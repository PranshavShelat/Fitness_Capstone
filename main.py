"""Desktop (OpenCV) launcher for the form engine.

The exercise menu and the analysis routing are both driven by engine.EXERCISES /
engine.analyze_frame, so adding an exercise to exercise_specs.py makes it appear
here automatically - there is no second list to keep in sync.
"""
import sys

import cv2
import mediapipe as mp

from engine import EXERCISES, analyze_frame, new_state
from utils import speak

print("--- AI Fitness Engine Launcher ---")
half = (len(EXERCISES) + 1) // 2
for i in range(half):
    left = f"{i + 1:2d}. {EXERCISES[i]['name']}"
    right = ""
    if i + half < len(EXERCISES):
        right = f"{i + half + 1:2d}. {EXERCISES[i + half]['name']}"
    print(f"{left:<26}{right}")

choice = input(f"\nSelect Exercise (1-{len(EXERCISES)}): ").strip()

try:
    CURRENT_MODE = EXERCISES[int(choice) - 1]["id"]
except (ValueError, IndexError):
    print("Invalid choice. Exiting.")
    sys.exit()

mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose
cap = cv2.VideoCapture(0)

with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
    state = new_state(CURRENT_MODE)

    print(f"\nStarting {CURRENT_MODE} Mode. Press 'q' on the video window to quit.")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image.flags.writeable = False
        results = pose.process(image)

        image.flags.writeable = True
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        try:
            if results.pose_landmarks:
                landmarks = results.pose_landmarks.landmark
                fb, clr, state, tel = analyze_frame(CURRENT_MODE, landmarks, state)

                speak(fb)

                cv2.rectangle(image, (0, 0), (640, 115), (0, 0, 0), -1)
                cv2.putText(image, f"EXERCISE: {CURRENT_MODE}", (10, 25),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
                cv2.putText(image, fb, (10, 70),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, clr, 2, cv2.LINE_AA)
                for i, stat in enumerate(tel):
                    cv2.putText(image, stat, (10, 95 + (i * 18)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

        except Exception:
            pass

        cv2.imshow('AI Fitness Engine', image)

        if cv2.waitKey(10) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()
