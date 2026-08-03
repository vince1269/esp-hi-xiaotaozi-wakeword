# Device overview

- Device: ESP-HI Xiaozhi AI robotic dog
- Main controller: ESP32-C3
- Frameworks: ESP-IDF, ESP-SR, and Xiaozhi ESP32
- Current offline wake word: standard Chinese WakeNet9s “你好小智”
- Target: obtain a WakeNet9s model for “小桃子” that is explicitly compatible with ESP32-C3

The preferred delivery is an ESP-SR model-directory entry or a resource that can be integrated into the device's Assets/model partition. This repository does not contain firmware credentials, device identifiers, account configuration, Wi-Fi settings, API keys, tokens, or other private device data.

The project is willing to test and report wake-up rate, false activation rate, speaking distance, environmental-noise behavior, and runtime stability on a real ESP-HI device.
