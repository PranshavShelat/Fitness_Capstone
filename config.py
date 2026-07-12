import csv
import numpy as np
from utils import calculate_angle

# --- 1. THE UNIVERSAL DATA EXTRACTOR ---
def extract_golden_target(csv_path, joints, movement_type="flexion"):
    angles = []
    try:
        with open(csv_path, 'r') as f:
            reader = csv.reader(f)
            next(reader) 
            for row in reader:
                a = [float(row[joints[0]*4]), float(row[joints[0]*4+1])]
                b = [float(row[joints[1]*4]), float(row[joints[1]*4+1])]
                c = [float(row[joints[2]*4]), float(row[joints[2]*4+1])]
                
                angle = calculate_angle(a, b, c)
                if 20 < angle < 180: # Ignore AI tracking glitches
                    angles.append(angle)
                    
        if not angles: 
            return 90.0 # Safe fallback
        
        # Flexion: Lowest angle achieved (e.g., bottom of a squat)
        if movement_type == "flexion":
            return np.mean([a for a in angles if a < (min(angles) + 10)])
            
        # Extension: Highest angle achieved (e.g., top of a press)
        elif movement_type == "extension":
            return np.mean([a for a in angles if a > (max(angles) - 10)])
            
        # Static: Average hold angle (e.g., a plank)
        elif movement_type == "static":
            return np.mean(angles)
            
    except FileNotFoundError:
        print(f"Warning: {csv_path} missing.")
        return 90.0

# --- 2. SQUAT ---
SQUAT_DEPTH = extract_golden_target('golden_dataset/Squats.csv', [24, 26, 28], "flexion")
SQUAT_SETTINGS = {
    "STAND": 160, "GOOD_MAX": SQUAT_DEPTH + 25, "GOOD_MIN": SQUAT_DEPTH - 10,
    "BACK_TOO_UPRIGHT": 5, "BACK_PERFECT_MAX": 45, "BACK_WARNING_MAX": 60, "TARGET_DEPTH": SQUAT_DEPTH
}

# --- 3. PLANK ---
PLANK_HIP = extract_golden_target('golden_dataset/Plank.csv', [12, 24, 26], "static")
PLANK_KNEE = extract_golden_target('golden_dataset/Plank.csv', [24, 26, 28], "static")
PLANK_SETTINGS = {"HIP_MIN": PLANK_HIP - 10, "KNEE_MIN": PLANK_KNEE - 10}

# --- 4. TRICEP DIPS ---
DIP_TARGET = extract_golden_target('golden_dataset/Tricep dips.csv', [12, 14, 16], "flexion")
DIP_SETTINGS = {"UP_STATE": 150, "TARGET_DEPTH": DIP_TARGET, "BUFFER": 15}

# --- 5. PUSHUPS ---
PUSHUP_ELBOW = extract_golden_target('golden_dataset/Pushups.csv', [12, 14, 16], "flexion")
PUSHUP_SETTINGS = {"UP_STATE": 150, "TARGET_DEPTH": PUSHUP_ELBOW, "BUFFER": 25, "HIP_MIN": 150}

# --- 6. PULLUPS ---
PULLUP_TARGET = extract_golden_target('golden_dataset/Pullups.csv', [12, 14, 16], "flexion")
PULLUP_SETTINGS = {"HANG_STATE": 150, "TARGET_TOP": PULLUP_TARGET, "BUFFER": 20}

# --- 7. RUSSIAN TWISTS ---
TWIST_CORE = extract_golden_target('golden_dataset/Russian twists.csv', [12, 24, 26], "static")
TWIST_SETTINGS = {"TARGET_POSTURE": TWIST_CORE, "BUFFER": 15}

# --- 8. BICEP CURLS ---
BICEP_TARGET = extract_golden_target('golden_dataset/Barbell bicep curl.csv', [12, 14, 16], "flexion")
BICEP_SETTINGS = {"EXTENDED": 150, "TARGET_FLEX": BICEP_TARGET, "BUFFER": 15}

# --- 9. HAMMER CURLS ---
HAMMER_TARGET = extract_golden_target('golden_dataset/Hammer curl.csv', [12, 14, 16], "flexion")
HAMMER_SETTINGS = {"EXTENDED": 150, "TARGET_FLEX": HAMMER_TARGET, "BUFFER": 15}

# --- 10. LATERAL RAISES ---
LATERAL_TARGET = extract_golden_target('golden_dataset/Lateral raise.csv', [24, 12, 14], "extension")
SAFE_LATERAL_TARGET = min(LATERAL_TARGET - 10, 85)
LATERAL_SETTINGS = {"DOWN": 30, "TARGET_UP": SAFE_LATERAL_TARGET, "BUFFER": 15, "ELBOW_MIN": 140}

# --- 11. SHOULDER PRESS ---
PRESS_TARGET = extract_golden_target('golden_dataset/Shoulder press.csv', [12, 14, 16], "extension")
PRESS_SETTINGS = {"START": 90, "TARGET_EXTENSION": PRESS_TARGET, "BUFFER": 15}

# --- 12. BENCH PRESS ---
BENCH_TARGET = extract_golden_target('golden_dataset/Benchpress.csv',[12, 14, 16],"flexion")
BENCH_SETTINGS = {"LOCKOUT": 165,"TARGET_DEPTH": BENCH_TARGET,"BUFFER": 15,"MAX_ASYMMETRY": 40,"MAX_FLARE": 85}