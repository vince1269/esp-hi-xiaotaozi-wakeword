#!/usr/bin/env python3
"""Deduplicated monitor for the ESP-SR '小桃子' WakeNet9s request."""

from __future__ import annotations

import json
import hashlib
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.github.com"
UPSTREAM = "espressif/esp-sr"
ISSUE = 88
STATE_PATH = Path(__file__).with_name("state.json")
TIMEOUT = 25
TERMS = ("小桃子", "xiaotaozi", "xiao tao zi", "wn9s_xiaotaozi", "wn9_xiaotaozi")
MODEL_HINTS = ("model", "wakenet", "wakenet_model", "wn9", "wn9s", "assets")


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_state() -> dict:
    return {"application_comment_id": None, "application_comment_url": None,
            "last_checked_at": None, "last_seen_comment_id": 0,
            "known_event_ids": [], "model_found": False, "model_paths": [],
            "release_matches": [], "issue_state": "open", "consecutive_failures": 0,
            "application_body_sha256": None, "application_comment_updated_at": None}


def load_state() -> dict:
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        base = default_state(); base.update(data if isinstance(data, dict) else {})
        return base
    except (OSError, json.JSONDecodeError):
        print("State file unreadable; recovering with safe defaults", file=sys.stderr)
        return default_state()


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def request(path: str, method: str = "GET", payload: dict | None = None):
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "xiaotaozi-wakeword-monitor",
               "X-GitHub-Api-Version": "2022-11-28"}
    if token: headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(API + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            return json.load(response), dict(response.headers)
    except urllib.error.HTTPError as exc:
        remaining = exc.headers.get("X-RateLimit-Remaining")
        reset = exc.headers.get("X-RateLimit-Reset")
        if exc.code == 403 and remaining == "0" and reset:
            raise RuntimeError(f"GitHub API rate limit reached; resets at {reset}") from exc
        raise RuntimeError(f"GitHub API HTTP {exc.code} for {path}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"GitHub API request failed for {path}: {type(exc).__name__}") from exc


def paged(path: str, limit: int = 10) -> list:
    items = []
    for page in range(1, limit + 1):
        sep = "&" if "?" in path else "?"
        batch, _ = request(f"{path}{sep}per_page=100&page={page}")
        if not isinstance(batch, list): break
        items.extend(batch)
        if len(batch) < 100: break
    return items


def relevant(text: str) -> bool:
    value = text.casefold()
    return any(term.casefold() in value for term in TERMS)


def post_tracking(repo: str, tracking_number: int, body: str) -> None:
    request(f"/repos/{repo}/issues/{tracking_number}/comments", "POST", {"body": body})


def main() -> int:
    state = load_state(); known = set(map(str, state.get("known_event_ids", [])))
    events = []
    try:
        issue, _ = request(f"/repos/{UPSTREAM}/issues/{ISSUE}")
        new_issue_state = issue.get("state", "unknown") + ("-locked" if issue.get("locked") else "")
        if state.get("issue_state") and new_issue_state != state["issue_state"]:
            events.append((f"issue:{new_issue_state}", "Issue status changed", issue["html_url"], new_issue_state, True,
                           "Review the official issue and identify any replacement submission channel."))
        state["issue_state"] = new_issue_state

        comments = paged(f"/repos/{UPSTREAM}/issues/{ISSUE}/comments")
        app_id = state.get("application_comment_id")
        app_comment = next((c for c in comments if c.get("id") == app_id), None) if app_id else None
        if app_id and not app_comment:
            events.append((f"application-missing:{app_id}", "Application comment unavailable", state.get("application_comment_url") or issue["html_url"],
                           "The original application comment could not be found.", True, "Check whether it was hidden, deleted, or migrated."))
        if app_comment:
            body_hash = hashlib.sha256((app_comment.get("body") or "").encode("utf-8")).hexdigest()
            old_hash = state.get("application_body_sha256")
            if old_hash and old_hash != body_hash:
                events.append((f"application-modified:{body_hash}", "Application comment modified",
                               app_comment["html_url"], "The application comment body changed.", True,
                               "Review the change and confirm all ESP32-C3 and WakeNet9s details remain accurate."))
            state["application_body_sha256"] = body_hash
            state["application_comment_updated_at"] = app_comment.get("updated_at")
        for c in comments:
            cid = int(c.get("id", 0)); state["last_seen_comment_id"] = max(state.get("last_seen_comment_id", 0), cid)
            body = c.get("body") or ""
            mentions_app = app_id and (str(app_id) in body or state.get("application_comment_url", "") in body)
            assoc = c.get("author_association", "NONE")
            official = assoc in {"OWNER", "MEMBER", "COLLABORATOR", "CONTRIBUTOR"}
            if cid != app_id and (mentions_app or (relevant(body) and official)):
                summary = re.sub(r"\s+", " ", body).strip()[:500]
                events.append((f"comment:{cid}", "Relevant maintainer/contributor reply" if official else "Relevant reply",
                               c["html_url"], summary, True, "Review and respond only if additional information is requested."))

        tree, _ = request(f"/repos/{UPSTREAM}/git/trees/master?recursive=1")
        for item in tree.get("tree", []):
            path = item.get("path", ""); low = path.casefold()
            if any(h in low for h in MODEL_HINTS) and relevant(path):
                events.append((f"path:{path}", "Possible wake-word model file", f"https://github.com/{UPSTREAM}/blob/master/{urllib.parse.quote(path)}",
                               path, True, "Verify model family and explicit ESP32-C3 compatibility before integration."))
                if path not in state["model_paths"]: state["model_paths"].append(path)

        releases = paged(f"/repos/{UPSTREAM}/releases", limit=3)
        for release in releases:
            haystack = " ".join([release.get("name") or "", release.get("tag_name") or "", release.get("body") or ""])
            if relevant(haystack):
                rid = release["id"]
                events.append((f"release:{rid}", "Relevant ESP-SR release", release["html_url"],
                               (release.get("name") or release.get("tag_name") or "release")[:300], True,
                               "Inspect assets and confirm WakeNet9s and ESP32-C3 support."))
                if rid not in state["release_matches"]: state["release_matches"].append(rid)

        repo = os.environ.get("TRACKING_REPOSITORY", "")
        tracking = int(os.environ.get("TRACKING_ISSUE_NUMBER", "1"))
        for event_id, kind, source, summary, human, next_step in events:
            if event_id in known: continue
            post_tracking(repo, tracking, f"## Wake-word monitor event\n\n- Discovered: {now()}\n- Event type: {kind}\n- Source: {source}\n- Summary: {summary}\n- Human action required: {'Yes' if human else 'No'}\n- Recommended next step: {next_step}")
            known.add(event_id)
        state["known_event_ids"] = sorted(known)
        state["model_found"] = bool(state["model_paths"])
        state["last_checked_at"] = now(); state["consecutive_failures"] = 0
        save_state(state)
        print(f"Monitor completed: {len(events)} candidate event(s), {len(known)} known event(s)")
        return 0
    except Exception as exc:
        state["last_checked_at"] = now(); state["consecutive_failures"] = int(state.get("consecutive_failures", 0)) + 1
        if state["consecutive_failures"] >= 2:
            event_id = f"failure-streak:{state['consecutive_failures']}"
            if event_id not in known:
                try:
                    repo = os.environ.get("TRACKING_REPOSITORY", "")
                    tracking = int(os.environ.get("TRACKING_ISSUE_NUMBER", "1"))
                    post_tracking(repo, tracking, f"## Wake-word monitor event\n\n- Discovered: {now()}\n- Event type: Repeated monitor failure\n- Source: https://github.com/{repo}/actions\n- Summary: The monitor has failed {state['consecutive_failures']} consecutive times.\n- Human action required: Yes\n- Recommended next step: Inspect the latest Actions logs and GitHub API availability.")
                    known.add(event_id); state["known_event_ids"] = sorted(known)
                except Exception:
                    pass
        save_state(state)
        print(f"Monitor failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
