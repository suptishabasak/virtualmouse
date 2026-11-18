# Gesture-Controlled Virtual Mouse

A computer-vision project that uses hand tracking to control the mouse pointer and selected system settings through hand gestures.

## Features

- Move the cursor using the right hand
- Perform left and right clicks using gestures
- Adjust system volume using the left hand
- Adjust screen brightness using the left hand
- Real-time hand landmark visualisation

## Requirements

- Python 3.9 or a compatible Python version supported by your installed MediaPipe release
- Webcam
- Windows is recommended for the volume-control functionality (`pycaw` and `comtypes`)

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run

```bash
python virtualmouse.py
```

Press `q` in the camera window to quit.

## Gesture controls

### Right hand — mouse

- Index finger up, middle finger down: move cursor
- Thumb and index finger pinched: left click
- Index and middle fingers up with tips close together: right click

### Left hand — system controls

- Pinky down: adjust volume using thumb-index distance
- Pinky up: adjust brightness using thumb-index distance

## How it works

The program detects hand landmarks with MediaPipe Tasks, maps landmark positions to screen coordinates, and uses PyAutoGUI for cursor and click actions. Pinch distance is mapped to volume or brightness levels.

The MediaPipe hand-landmarker task model is downloaded automatically on first run.

## Notes

Volume and brightness controls depend on operating-system and hardware support. The volume implementation uses Windows-specific libraries.
