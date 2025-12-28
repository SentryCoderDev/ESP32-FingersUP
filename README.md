# ESP32-FingersUP

A small project that uses a PC webcam and OpenCV-based hand-gesture detection to send 5-bit gesture messages over MQTT to an ESP microcontroller that controls LEDs.

## Overview

The publisher runs on a PC (Python + OpenCV). It detects which fingers are up and publishes a 5-character string such as `01010` to an MQTT topic. An ESP8266/ESP32 subscriber listens to the topic and toggles five LEDs according to the received bits.

## Features

- Detects five fingers and encodes their state as a 5-bit string (thumb..pinky).
- Publishes changes only (reduces MQTT chatter).
- Simple Arduino/ESP sketch included to subscribe and control GPIO pins.

## Requirements

- Python 3.8+
- A webcam (or other camera accessible by OpenCV)
- An ESP8266 or ESP32 board with WiFi
- MQTT broker (public example: `broker.emqx.io`) or your own broker

## Python dependencies

Install dependencies in a virtual environment:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Quick start (publisher)

1. Adjust broker/topic if needed in `Publisher.py` or call the package programmatically.
2. Run the publisher (this opens the webcam window):

```bash
python Publisher.py
```

Press `q` to quit.

Output example published to MQTT:

```
Publish Message: 01010
```

## Quick start (ESP subscriber)

- The Arduino sketch is at `ESP8266_Subscriber/ESP32-Subscriber/ESP32-Subscriber.ino`.
- Update `ssid`, `password` and (optionally) the MQTT topic in the sketch before uploading.
- The sketch expects a 5-character payload and writes each character to a configured GPIO pin.

## Project structure

- `Publisher.py` — thin wrapper that calls the modular `publisher` package
- `publisher/` — modular code (camera, detector, mqtt client, main)
- `ESP8266_Subscriber/` — Arduino sketch for the ESP
- `requirements.txt` — Python dependencies
- `Wiring ESP32.jpg` — wiring reference image (can be moved to `docs/`)

## Notes and suggestions

- The repo currently contains a compiled bytecode file in `publisher/__pycache__` — add a `.gitignore` and remove `__pycache__` from version control.
- If you use your own MQTT broker, update `publisher/mqtt_client.py` or pass broker/topic to `publisher.main.run()`.

## License

This project includes a `LICENSE` file. Check it for reuse terms.

