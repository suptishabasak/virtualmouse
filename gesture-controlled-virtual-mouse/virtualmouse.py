"""
Hand-gesture virtual mouse + volume/brightness controller (MediaPipe Tasks API).

RIGHT HAND (mouse)
  - Index up, middle down ............ move cursor
  - Pinch thumb + index .............. left click
  - Index + middle up, tips together . right click

LEFT HAND (controller)
  - Pinky down: thumb-index distance . volume
  - Pinky up:   thumb-index distance . brightness

Press 'q' in the video window to quit.

Install:
  pip install opencv-python mediapipe pyautogui numpy screen-brightness-control pycaw comtypes
"""

import math
import os
import time
import urllib.request

import cv2
import mediapipe as mp
import numpy as np
import pyautogui
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

# ---------- model download (one time, ~8 MB) ----------
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hand_landmarker.task")
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/1/hand_landmarker.task")
if not os.path.exists(MODEL_PATH):
    print("Downloading hand model...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)

# ---------- brightness ----------
try:
    import screen_brightness_control as sbc
except ImportError:
    sbc = None


def set_brightness(pct):
    if sbc:
        try:
            sbc.set_brightness(int(pct))
        except Exception:
            pass


# ---------- volume (Windows / pycaw) ----------
set_volume = None
try:
    from ctypes import POINTER, cast
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    speakers = AudioUtilities.GetSpeakers()
    if hasattr(speakers, "EndpointVolume"):          # newer pycaw
        _vol = speakers.EndpointVolume
    else:                                            # older pycaw
        _iface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        _vol = cast(_iface, POINTER(IAudioEndpointVolume))

    def set_volume(pct):
        _vol.SetMasterVolumeLevelScalar(float(np.clip(pct, 0, 100)) / 100.0, None)
except Exception as e:
    print("Volume control unavailable:", e)

# ---------- config ----------
CAM_W, CAM_H = 640, 480
FRAME_MARGIN = 100
SMOOTHING = 5
CLICK_DIST = 30
CLICK_COOLDOWN = 0.4
PINCH_MIN, PINCH_MAX = 25, 200
CONTROL_SMOOTH = 0.2

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0
screen_w, screen_h = pyautogui.size()

THUMB_TIP, INDEX_TIP, MIDDLE_TIP = 4, 8, 12
PIPS = {"index": (8, 6), "middle": (12, 10), "ring": (16, 14), "pinky": (20, 18)}

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12), (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
]


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def fingers_up(lm):
    return {f: lm[tip].y < lm[pip].y for f, (tip, pip) in PIPS.items()}


def draw_hand(frame, pts):
    for a, b in HAND_CONNECTIONS:
        cv2.line(frame, pts[a], pts[b], (0, 255, 0), 2)
    for p in pts:
        cv2.circle(frame, p, 4, (255, 0, 255), cv2.FILLED)


def main():
    options = vision.HandLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.7,
        min_tracking_confidence=0.6,
    )
    landmarker = vision.HandLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(0)
    cap.set(3, CAM_W)
    cap.set(4, CAM_H)

    prev_x, prev_y = 0.0, 0.0
    last_click = 0.0
    vol_level, bri_level = 50.0, 50.0
    status = ""
    start = time.time()

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = landmarker.detect_for_video(mp_img, int((time.time() - start) * 1000))

        cv2.rectangle(frame, (FRAME_MARGIN, FRAME_MARGIN),
                      (w - FRAME_MARGIN, h - FRAME_MARGIN), (255, 0, 255), 2)

        for lm, handed in zip(result.hand_landmarks, result.handedness):
            label = handed[0].category_name  # "Left" / "Right"
            pts = [(int(p.x * w), int(p.y * h)) for p in lm]
            draw_hand(frame, pts)

            thumb, index, middle = pts[THUMB_TIP], pts[INDEX_TIP], pts[MIDDLE_TIP]
            up = fingers_up(lm)

            # ---------- RIGHT HAND: MOUSE ----------
            if label == "Right":
                if up["index"] and not up["middle"]:
                    tx = np.interp(index[0], (FRAME_MARGIN, w - FRAME_MARGIN), (0, screen_w))
                    ty = np.interp(index[1], (FRAME_MARGIN, h - FRAME_MARGIN), (0, screen_h))
                    prev_x += (tx - prev_x) / SMOOTHING
                    prev_y += (ty - prev_y) / SMOOTHING
                    pyautogui.moveTo(prev_x, prev_y)
                    status = "Mouse: move"

                    if dist(thumb, index) < CLICK_DIST and time.time() - last_click > CLICK_COOLDOWN:
                        pyautogui.click()
                        last_click = time.time()
                        status = "Mouse: LEFT CLICK"
                        cv2.circle(frame, index, 15, (0, 255, 0), cv2.FILLED)

                elif up["index"] and up["middle"]:
                    if dist(index, middle) < CLICK_DIST and time.time() - last_click > CLICK_COOLDOWN:
                        pyautogui.rightClick()
                        last_click = time.time()
                        status = "Mouse: RIGHT CLICK"
                        cv2.circle(frame, index, 15, (0, 0, 255), cv2.FILLED)

            # ---------- LEFT HAND: VOLUME / BRIGHTNESS ----------
            elif label == "Left":
                d = dist(thumb, index)
                target = float(np.interp(d, [PINCH_MIN, PINCH_MAX], [0, 100]))
                cv2.line(frame, thumb, index, (255, 255, 0), 3)

                if up["pinky"]:
                    bri_level += (target - bri_level) * CONTROL_SMOOTH
                    set_brightness(bri_level)
                    status = f"Brightness: {int(bri_level)}%"
                else:
                    vol_level += (target - vol_level) * CONTROL_SMOOTH
                    if set_volume:
                        set_volume(vol_level)
                    status = f"Volume: {int(vol_level)}%"

        cv2.putText(frame, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.imshow("Hand Controller", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()