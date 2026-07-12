import cv2
import mediapipe as mp
import sys
import time
from engine import (
    analyze_squat, analyze_plank, analyze_tricep_dip, 
    analyze_pushup, analyze_pullup, analyze_russian_twist,
    analyze_bicep_curl, analyze_hammer_curl, 
    analyze_lateral_raise, analyze_shoulder_press,analyze_bench_press
)
from utils import speak, smooth_landmarks, debounce_stage, stabilize_feedback, build_common_telemetry

# --- TERMINAL SELECTION MENU ---
print("1. Squats              12. Chest Fly Machine")
print("2. Planks              13. Deadlift")
print("3. Tricep Dips         14. Decline Bench Press")
print("4. Pushups             15. Hip Thrust")
print("5. Pullups             16. Inclined Bench Press")
print("6. Russian Twists      17. Lat Pulldown")
print("7. Bicep Curls         18. Leg Extension")
print("8. Hammer Curls        19. Leg Raises")
print("9. Lateral Raises      20. Romanian Deadlifts")
print("10. Shoulder Press     21. T Bar Row")
print("11. Bench Press        22. Tricep Pushdowns")

choice = input("\nSelect Exercise (1-10): ")

modes = {
    "1": "SQUAT", "2": "PLANK", "3": "DIP", "4": "PUSHUP", 
    "5": "PULLUP", "6": "TWIST", "7": "BICEP", "8": "HAMMER", 
    "9": "LATERAL", "10": "PRESS","11": "BENCH"
}

CURRENT_MODE = modes.get(choice)

if not CURRENT_MODE:
    print("Invalid choice. Exiting.")
    sys.exit()

# --- SYSTEM INITIALIZATION ---
mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose
cap = cv2.VideoCapture("bench press_28.mp4")

with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
    stage = "UP"
    prev_back = 0

    # --- ENGINE-WIDE STATE (benefits every exercise, present + future) ---
    prev_smoothed = None      # landmark EMA state, for smooth_landmarks()
    stage_pending = None      # hysteresis state, for debounce_stage()
    feedback_state = None     # hold state, for stabilize_feedback()
    prev_frame_time = time.time()
    
    print(f"\nStarting {CURRENT_MODE} Mode. Press 'q' on the video window to quit.")
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: 
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        # --- FRAME TIMING (drives adaptive smoothing + FPS telemetry) ---
        now = time.time()
        frame_dt = now - prev_frame_time if now > prev_frame_time else None
        fps = (1.0 / frame_dt) if frame_dt else None
        prev_frame_time = now

        # Recolor image to RGB for MediaPipe
        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image.flags.writeable = False
        results = pose.process(image)
        
        # Recolor back to BGR for OpenCV display
        image.flags.writeable = True
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        
        try:
            if results.pose_landmarks:
                # --- LANDMARK SMOOTHING (Problem 1) ---
                # Drop-in replacement for the raw landmark list: still
                # supports .x / .y, so every analyze_*() below is unaffected.
                landmarks, prev_smoothed = smooth_landmarks(
                    results.pose_landmarks.landmark, prev_smoothed, dt=frame_dt
                )
                
                # --- DYNAMIC EXERCISE ROUTING ---
                # raw_stage is set to None for exercises with no stage
                # machine (Plank, Twist) so the debounce step below can
                # skip them safely.
                if CURRENT_MODE == "SQUAT":
                    fb, clr, raw_stage, prev_back, tel = analyze_squat(landmarks, stage, prev_back)
                elif CURRENT_MODE == "PLANK":
                    fb, clr, tel = analyze_plank(landmarks)
                    raw_stage = None
                elif CURRENT_MODE == "DIP":
                    fb, clr, raw_stage, tel = analyze_tricep_dip(landmarks, stage)
                elif CURRENT_MODE == "PUSHUP":
                    fb, clr, raw_stage, tel = analyze_pushup(landmarks, stage)
                elif CURRENT_MODE == "PULLUP":
                    fb, clr, raw_stage, tel = analyze_pullup(landmarks, stage)
                elif CURRENT_MODE == "TWIST":
                    fb, clr, tel = analyze_russian_twist(landmarks)
                    raw_stage = None
                elif CURRENT_MODE == "BICEP":
                    fb, clr, raw_stage, tel = analyze_bicep_curl(landmarks, stage)
                elif CURRENT_MODE == "HAMMER":
                    fb, clr, raw_stage, tel = analyze_hammer_curl(landmarks, stage)
                elif CURRENT_MODE == "LATERAL":
                    fb, clr, raw_stage, tel = analyze_lateral_raise(landmarks, stage)
                elif CURRENT_MODE == "PRESS":
                    fb, clr, raw_stage, tel = analyze_shoulder_press(landmarks, stage)
                elif CURRENT_MODE == "BENCH":
                    fb, clr, raw_stage, tel = analyze_bench_press(landmarks, stage)

                # --- STAGE HYSTERESIS (Problem 2) ---
                # Applies automatically to whichever exercise is active,
                # and to any future exercise that returns a stage.
                if raw_stage is not None:
                    stage, stage_pending = debounce_stage(raw_stage, stage, stage_pending)

                # --- FEEDBACK STABILIZATION (Problem 3) ---
                # Danger (red) feedback always passes through instantly;
                # everything else is debounced against flicker.
                fb, clr, feedback_state = stabilize_feedback(fb, clr, feedback_state)

                # --- COMMON TELEMETRY (Problem 5) ---
                tel = tel + build_common_telemetry(stage, landmarks, fps)

                # --- AUDIO FEEDBACK ---
                speak(fb)
                
                # --- UI RENDERING ---
                cv2.rectangle(image, (0,0), (640, 115), (0,0,0), -1)
                
                cv2.putText(image, f"EXERCISE: {CURRENT_MODE}", (10, 25), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
                            
                cv2.putText(image, fb, (10, 70), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2, clr, 3, cv2.LINE_AA)
                
                for i, stat in enumerate(tel):
                    cv2.putText(image, stat, (10, 95 + (i*18)), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
                    
            mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
            
        except Exception as e: 
            pass 
            
        cv2.imshow('AI Fitness Engine', image)
        
        if cv2.waitKey(10) & 0xFF == ord('q'): 
            break

cap.release()
cv2.destroyAllWindows()