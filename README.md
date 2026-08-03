# ESP-HI 小桃子 WakeNet9s Wake Word

This repository tracks a WakeNet9s wake-word request for a personal, non-commercial ESP-HI robotic dog project based on ESP32-C3.

- Device: ESP-HI AI robotic dog
- Chip: ESP32-C3
- Frameworks: ESP-IDF, ESP-SR, WakeNet9s, Xiaozhi ESP32
- Current wake word: “你好小智”
- Requested wake word: “小桃子” (`xiao3 tao2 zi5`)
- Existing capabilities: cloud voice conversations, screen expressions, lights, and MCP-controlled movements
- Scope: request and integrate a compatible WakeNet9s model only; no robotic movement firmware changes are requested

## Application status

- Status: Submitted; awaiting upstream response
- Official application: https://github.com/espressif/esp-sr/issues/88#issuecomment-5164128467
- Tracking issue: https://github.com/vince1269/esp-hi-xiaotaozi-wakeword/issues/1

[![Monitor wake word](https://github.com/vince1269/esp-hi-xiaotaozi-wakeword/actions/workflows/monitor-wakeword.yml/badge.svg)](https://github.com/vince1269/esp-hi-xiaotaozi-wakeword/actions/workflows/monitor-wakeword.yml)

## Run the monitor manually

Open **Actions → Monitor ESP-SR wake word → Run workflow**. The workflow also runs every six hours and only posts newly detected, relevant events to the tracking issue.

See [APPLICATION.md](APPLICATION.md) and [docs/device-overview.md](docs/device-overview.md).
