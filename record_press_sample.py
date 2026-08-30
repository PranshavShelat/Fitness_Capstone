"""
One-off DEV TOOL - not part of the shipped app. Records real shoulder-press
landmarks straight from your own webcam into calibration_data/press_good.csv,
press_forward.csv and press_back.csv, in the same 33-landmark x/y/z/v format
as golden_dataset/*.csv.

Just run it - no arguments:
    python record_press_sample.py

All three recordings, once they exist, are picked up automatically by
config.py's PRESS_ELBOW_FORWARD_REFERENCE / PRESS_ELBOW_BACK_REFERENCE the
next time the server starts - no other wiring needed. You don't need all
three at once: forward-only or back-only recordings still enable that one
check, whichever one has both "good" and its matching fault recorded.

Controls (in the preview window):
    g        toggle recording GOOD form (correct - elbows rotate back)
    f        toggle recording the ELBOWS TOO FAR FORWARD fault
    k        toggle recording the ELBOWS TOO FAR BACK fault
    q / ESC  quit and save everything recorded

Only one mode can be "on" at a time - pressing another key switches to it
directly, no need to pause first. Do a few reps of each, switching back and
forth as many times as you like before quitting. Keep each fault in its OWN
recording - don't mix "too forward" and "too back" reps together under the
same key, that corrupts the boundary for both.
"""
import csv
import os
import sys
import time

import cv2
import mediapipe as mp

from engine import press_elbow_forward_signal

CALIBRATION_DIR = "calibration_data"

MODE_KEYS = {ord('g'): 'good', ord('f'): 'forward', ord('k'): 'back'}
MODE_COLORS = {'good': (0, 200, 0), 'forward': (0, 0, 255), 'back': (255, 130, 0), None: (90, 90, 90)}

INSTRUCTIONS = (
    "'g' = GOOD form   'f' = ELBOWS TOO FAR FORWARD   'k' = ELBOWS TOO FAR BACK   'q' = save & quit"
)

WHITE = (255, 255, 255)
YELLOW = (0, 220, 255)

WINDOW_NAME = "Shoulder Press Calibration Recorder"

# How long the big "RECORDING ... STARTED" / "PAUSED" toast stays on screen
# after a toggle, separate from the always-on status bar so a quick glance
# mid-rep still confirms the toggle actually registered.
TOAST_SECONDS = 1.2

# OpenCV only reads key presses when THIS window (not the terminal) is
# focused. This banner stays up long enough for that to actually register
# before the "click the window" instruction disappears.
FOCUS_HINT_SECONDS = 5


def draw_toast(frame, text, color):
    h, w = frame.shape[:2]
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 3)
    x, y = (w - tw) // 2, h // 2
    cv2.rectangle(frame, (x - 20, y - th - 20), (x + tw + 20, y + 20), (0, 0, 0), -1)
    cv2.rectangle(frame, (x - 20, y - th - 20), (x + tw + 20, y + 20), color, 3)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3)


def save(label, rows):
    if not rows:
        return
    header = []
    for i in range(1, 34):
        header += [f"x{i}", f"y{i}", f"z{i}", f"v{i}"]

    os.makedirs(CALIBRATION_DIR, exist_ok=True)
    out_path = os.path.join(CALIBRATION_DIR, f"press_{label}.csv")
    file_exists = os.path.isfile(out_path)
    with open(out_path, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(header)
        writer.writerows(rows)
    print(f"Saved {len(rows)} frames to {out_path}")


def main():
    mp_pose = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils
    pose = mp_pose.Pose(model_complexity=1, min_detection_confidence=0.5, min_tracking_confidence=0.5)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open webcam. Is another app already using it exclusively?")
        sys.exit(1)

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    try:
        # Best-effort - not all OpenCV builds support this, but when it works
        # it keeps the window from opening hidden behind the terminal.
        cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_TOPMOST, 1)
    except Exception:
        pass

    mode = None  # None | 'good' | 'forward' | 'back' - which one is currently recording
    rows_by_mode = {'good': [], 'forward': [], 'back': []}
    toast_text, toast_color, toast_until = None, WHITE, 0.0
    start_time = time.time()
    read_failures = 0

    print("A video window should now be open.")
    print("IMPORTANT: click on that video window (not this terminal) before pressing any keys.")
    print(INSTRUCTIONS, "\n")

    while True:
        ok, frame = cap.read()
        if not ok:
            read_failures += 1
            if read_failures > 30:
                print("\nCamera stopped returning frames. On macOS, check System Settings > "
                      "Privacy & Security > Camera and make sure your terminal app is allowed.")
                break
            continue
        read_failures = 0

        frame = cv2.flip(frame, 1)  # selfie-view for the preview only
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb)

        if results.pose_landmarks:
            mp_drawing.draw_landmarks(frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

            if mode is not None:
                landmarks = results.pose_landmarks.landmark
                row = []
                for lm in landmarks:
                    row += [lm.x, lm.y, lm.z, lm.visibility]
                rows_by_mode[mode].append(row)

                angle, elbow_z = press_elbow_forward_signal(landmarks)
                cv2.putText(frame, f"Elbow: {angle:.0f} deg  elbowZ-shoulderZ: {elbow_z:.3f}",
                            (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 0), 2)

        mode_color = MODE_COLORS[mode]

        # Thick full-frame border while recording - visible in peripheral vision
        # without having to read any text, so there's no ambiguity mid-rep.
        if mode is not None:
            cv2.rectangle(frame, (0, 0), (w - 1, h - 1), mode_color, 12)

        # Always-on status bar (filled, not just text, so it reads clearly over
        # any background) - separate from the transient toast below.
        cv2.rectangle(frame, (0, 0), (w, 55), mode_color, -1)
        status = f"RECORDING {mode.upper()}" if mode else "PAUSED"
        counts = "  ".join(f"{k}: {len(v)}" for k, v in rows_by_mode.items())
        cv2.putText(frame, f"{status}  |  {counts}",
                    (15, 37), cv2.FONT_HERSHEY_SIMPLEX, 0.65, WHITE, 2)

        cv2.putText(frame, INSTRUCTIONS, (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, WHITE, 1)

        # Big, hard-to-miss reminder for the first few seconds: keys only work
        # if THIS window has focus, not the terminal that launched it.
        if time.time() - start_time < FOCUS_HINT_SECONDS:
            draw_toast(frame, "CLICK THIS WINDOW, then press g / f / k", YELLOW)
        elif toast_text and time.time() < toast_until:
            draw_toast(frame, toast_text, toast_color)

        cv2.imshow(WINDOW_NAME, frame)
        key = cv2.waitKey(1) & 0xFF
        if key in MODE_KEYS:
            start_time = 0  # first real keypress registered - stop showing the focus hint
            pressed = MODE_KEYS[key]
            mode = None if mode == pressed else pressed
            if mode:
                toast_text = f"* RECORDING {mode.upper()} STARTED"
                toast_color = MODE_COLORS[mode]
            else:
                toast_text, toast_color = "PAUSED", MODE_COLORS[None]
            counts = ", ".join(f"{k}: {len(v)}" for k, v in rows_by_mode.items())
            print(f"{'RECORDING ' + mode.upper() if mode else 'PAUSED'} (so far - {counts})")
            toast_until = time.time() + TOAST_SECONDS
        elif key == ord('q') or key == 27:
            counts = " + ".join(f"{len(v)} {k}" for k, v in rows_by_mode.items())
            toast_text, toast_color = f"Saving {counts} frames...", YELLOW
            draw_toast(frame, toast_text, toast_color)
            cv2.imshow(WINDOW_NAME, frame)
            cv2.waitKey(1)
            break

    cap.release()
    cv2.destroyAllWindows()
    pose.close()

    if not any(rows_by_mode.values()):
        print("\nNo frames recorded - nothing saved.")
        print("Reminder: you have to click on the video window itself (not this terminal) "
              "before the keys will do anything - OpenCV only reads keys typed into its own window.")
        return

    for label, rows in rows_by_mode.items():
        save(label, rows)


if __name__ == "__main__":
    main()
