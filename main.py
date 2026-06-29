import cv2
import mediapipe as mp
import sys
from engine import (
    analyze_squat, analyze_plank, analyze_tricep_dip, 
    analyze_pushup, analyze_pullup, analyze_russian_twist,
    analyze_bicep_curl, analyze_hammer_curl, 
    analyze_lateral_raise, analyze_shoulder_press
)
from utils import speak

# --- TERMINAL SELECTION MENU ---
print("--- AI Fitness Engine Launcher ---")
print("1. Squats            6. Russian Twists")
print("2. Planks            7. Bicep Curls")
print("3. Tricep Dips       8. Hammer Curls")
print("4. Pushups           9. Lateral Raises")
print("5. Pullups          10. Shoulder Press")

choice = input("\nSelect Exercise (1-10): ")

modes = {
    "1": "SQUAT", "2": "PLANK", "3": "DIP", "4": "PUSHUP", 
    "5": "PULLUP", "6": "TWIST", "7": "BICEP", "8": "HAMMER", 
    "9": "LATERAL", "10": "PRESS"
}

CURRENT_MODE = modes.get(choice)

if not CURRENT_MODE:
    print("Invalid choice. Exiting.")
    sys.exit()

# --- SYSTEM INITIALIZATION ---
mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose
cap = cv2.VideoCapture(0)

with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
    stage = "UP"
    prev_back = 0
    
    print(f"\nStarting {CURRENT_MODE} Mode. Press 'q' on the video window to quit.")
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: 
            break
            
        # Recolor image to RGB for MediaPipe
        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image.flags.writeable = False
        results = pose.process(image)
        
        # Recolor back to BGR for OpenCV display
        image.flags.writeable = True
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        
        try:
            if results.pose_landmarks:
                landmarks = results.pose_landmarks.landmark
                
                # --- DYNAMIC EXERCISE ROUTING ---
                if CURRENT_MODE == "SQUAT":
                    fb, clr, stage, prev_back, tel = analyze_squat(landmarks, stage, prev_back)
                elif CURRENT_MODE == "PLANK":
                    fb, clr, tel = analyze_plank(landmarks)
                elif CURRENT_MODE == "DIP":
                    fb, clr, stage, tel = analyze_tricep_dip(landmarks, stage)
                elif CURRENT_MODE == "PUSHUP":
                    fb, clr, stage, tel = analyze_pushup(landmarks, stage)
                elif CURRENT_MODE == "PULLUP":
                    fb, clr, stage, tel = analyze_pullup(landmarks, stage)
                elif CURRENT_MODE == "TWIST":
                    fb, clr, tel = analyze_russian_twist(landmarks)
                elif CURRENT_MODE == "BICEP":
                    fb, clr, stage, tel = analyze_bicep_curl(landmarks, stage)
                elif CURRENT_MODE == "HAMMER":
                    fb, clr, stage, tel = analyze_hammer_curl(landmarks, stage)
                elif CURRENT_MODE == "LATERAL":
                    fb, clr, stage, tel = analyze_lateral_raise(landmarks, stage)
                elif CURRENT_MODE == "PRESS":
                    fb, clr, stage, tel = analyze_shoulder_press(landmarks, stage)
                    
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