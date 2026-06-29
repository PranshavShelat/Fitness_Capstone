import mediapipe as mp
import numpy as np
from utils import calculate_angle
from config import (
    SQUAT_SETTINGS, PLANK_SETTINGS, DIP_SETTINGS, 
    PUSHUP_SETTINGS, PULLUP_SETTINGS, TWIST_SETTINGS,
    BICEP_SETTINGS, HAMMER_SETTINGS, LATERAL_SETTINGS, PRESS_SETTINGS
)

mp_pose = mp.solutions.pose

# --- 1. SQUAT ---
def analyze_squat(landmarks, stage, prev_back_angle):
    r_hip = [landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y]
    r_knee = [landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].y]
    r_ankle = [landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].y]
    shoulder = [landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y]

    l_hip = [landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].x, landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y]
    l_knee = [landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].x, landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].y]

    live_leg = calculate_angle(r_hip, r_knee, r_ankle)
    dy, dx = r_hip[1] - shoulder[1], r_hip[0] - shoulder[0]
    back_angle = 0.8 * prev_back_angle + 0.2 * abs(np.arctan2(dx, dy) * 180.0 / np.pi)
    
    hip_width = abs(l_hip[0] - r_hip[0])
    knee_width = abs(l_knee[0] - r_knee[0])
    is_caving = (hip_width > 0.1) and (knee_width < (hip_width * 0.7))
    
    target = max(SQUAT_SETTINGS["TARGET_DEPTH"], 90)
    buffer_max = target + 15 
    buffer_min = target - 20 

    if live_leg > SQUAT_SETTINGS["STAND"]: stage = "UP"
    elif live_leg < buffer_max and stage == "UP": stage = "DOWN"

    feedback, color = "STAND READY", (255, 255, 255)
    
    if live_leg <= SQUAT_SETTINGS["STAND"]:
        if is_caving and live_leg < 140:
            feedback, color = "KNEES CAVING IN! (PUSH OUT)", (0, 0, 255)
        elif live_leg > buffer_max:
            if stage == "DOWN":
                feedback, color = "GO LOWER", (0, 165, 255)
            else:
                feedback, color = "STAND UP", (255, 255, 255)
        elif live_leg < buffer_min:
            feedback, color = "TOO DEEP (SPINE RISK)", (0, 0, 255)
        else:
            if back_angle > SQUAT_SETTINGS["BACK_WARNING_MAX"]:
                feedback, color = "DANGER: FORWARD LEAN", (0, 0, 255)
            elif back_angle > SQUAT_SETTINGS["BACK_PERFECT_MAX"]:
                feedback, color = "FIX FORWARD LEAN", (0, 255, 255)
            else:
                feedback, color = "PERFECT SQUAT!", (0, 255, 0)

    tel = [f"Leg: {int(live_leg)} (Must drop below: {int(buffer_max)})", f"Back: {int(back_angle)}"]
    return feedback, color, stage, back_angle, tel

# --- 2. PLANK ---
def analyze_plank(landmarks):
    hip = [landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y]
    knee = [landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].y]
    shoulder = [landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y]
    ankle = [landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].y]

    hip_angle = calculate_angle(shoulder, hip, knee)
    knee_angle = calculate_angle(hip, knee, ankle)

    feedback, color = "PERFECT PLANK", (0, 255, 0)
    if hip_angle < PLANK_SETTINGS["HIP_MIN"]: feedback, color = "STRAIGHTEN HIPS", (0, 0, 255)
    elif knee_angle < PLANK_SETTINGS["KNEE_MIN"]: feedback, color = "STRAIGHTEN KNEES", (0, 165, 255)

    tel = [f"Hip: {int(hip_angle)}", f"Knee: {int(knee_angle)}"]
    return feedback, color, tel

# --- 3. TRICEP DIPS ---
def analyze_tricep_dip(landmarks, stage):
    shoulder = [landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y]
    elbow = [landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].y]
    wrist = [landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].y]

    elbow_angle = calculate_angle(shoulder, elbow, wrist)

    if elbow_angle > DIP_SETTINGS["UP_STATE"]: stage = "UP"
    elif elbow_angle < DIP_SETTINGS["TARGET_DEPTH"] + DIP_SETTINGS["BUFFER"] and stage == "UP": stage = "DOWN"

    feedback, color = "READY", (255, 255, 255)
    if elbow_angle <= DIP_SETTINGS["UP_STATE"]:
        if elbow_angle > DIP_SETTINGS["TARGET_DEPTH"] + DIP_SETTINGS["BUFFER"]:
            feedback, color = "GO LOWER", (0, 0, 255)
        elif elbow_angle >= DIP_SETTINGS["TARGET_DEPTH"] - 10:
            feedback, color = "PERFECT DEPTH", (0, 255, 0)
        else:
            feedback, color = "TOO DEEP (SHOULDER RISK)", (0, 165, 255)

    return feedback, color, stage, [f"Elbow: {int(elbow_angle)}"]

# --- 4. PUSHUPS ---
def analyze_pushup(landmarks, stage):
    shoulder = [landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y]
    elbow = [landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].y]
    wrist = [landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].y]
    hip = [landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y]
    knee = [landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].y]

    elbow_angle = calculate_angle(shoulder, elbow, wrist)
    hip_angle = calculate_angle(shoulder, hip, knee)
    flare_angle = calculate_angle(hip, shoulder, elbow)

    if elbow_angle > PUSHUP_SETTINGS["UP_STATE"]: stage = "UP"
    elif elbow_angle < PUSHUP_SETTINGS["TARGET_DEPTH"] + PUSHUP_SETTINGS["BUFFER"] and stage == "UP": stage = "DOWN"

    feedback, color = "READY", (255, 255, 255)
    
    if hip_angle < PUSHUP_SETTINGS["HIP_MIN"]:
        feedback, color = "HIPS SAGGING", (0, 0, 255)
    elif flare_angle > 75:
        feedback, color = "TUCK ELBOWS (DON'T FLARE)", (0, 0, 255)
    elif elbow_angle > PUSHUP_SETTINGS["UP_STATE"] - 10:
        feedback, color = "ARMS EXTENDED (LOWER DOWN)", (255, 255, 255)
    elif elbow_angle > PUSHUP_SETTINGS["TARGET_DEPTH"] + PUSHUP_SETTINGS["BUFFER"]:
        if stage == "DOWN":
            feedback, color = "GO LOWER", (0, 165, 255)
        else:
            feedback, color = "PUSH BACK UP", (0, 255, 255) 
    else:
        feedback, color = "PERFECT PUSHUP DEPTH", (0, 255, 0)

    return feedback, color, stage, [f"Elbow: {int(elbow_angle)}", f"Flare: {int(flare_angle)} (Target: <75)"]

# --- 5. PULLUPS ---
def analyze_pullup(landmarks, stage):
    shoulder = [landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y]
    elbow = [landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].y]
    wrist = [landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].y]

    elbow_angle = calculate_angle(shoulder, elbow, wrist)

    if elbow_angle > PULLUP_SETTINGS["HANG_STATE"]: stage = "DOWN"
    elif elbow_angle < PULLUP_SETTINGS["TARGET_TOP"] + PULLUP_SETTINGS["BUFFER"] and stage == "DOWN": stage = "UP"

    feedback, color = "DEAD HANG", (255, 255, 255)
    if elbow_angle <= PULLUP_SETTINGS["HANG_STATE"]:
        if elbow_angle > PULLUP_SETTINGS["TARGET_TOP"] + PULLUP_SETTINGS["BUFFER"]:
            feedback, color = "PULL HIGHER", (0, 0, 255)
        else:
            feedback, color = "PERFECT REP", (0, 255, 0)

    return feedback, color, stage, [f"Elbow: {int(elbow_angle)}"]

# --- 6. RUSSIAN TWISTS ---
def analyze_russian_twist(landmarks):
    shoulder = [landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y]
    hip = [landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y]
    knee = [landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].y]

    v_angle = calculate_angle(shoulder, hip, knee)
    target = TWIST_SETTINGS["TARGET_POSTURE"]

    feedback, color = "PERFECT V-HOLD POSTURE", (0, 255, 0)
    if v_angle > target + TWIST_SETTINGS["BUFFER"]:
        feedback, color = "LEAN BACK MORE", (0, 0, 255)
    elif v_angle < target - TWIST_SETTINGS["BUFFER"]:
        feedback, color = "SITTING TOO FAR BACK", (0, 165, 255)

    return feedback, color, [f"Core Angle: {int(v_angle)}"]

# --- 7. BICEP CURLS ---
def analyze_bicep_curl(landmarks, stage):
    h = [landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y]
    s = [landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y]
    e = [landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].y]
    w = [landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].y]
    
    thumb = [landmarks[mp_pose.PoseLandmark.RIGHT_THUMB.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_THUMB.value].y]
    pinky = [landmarks[mp_pose.PoseLandmark.RIGHT_PINKY.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_PINKY.value].y]
    
    elbow_angle = calculate_angle(s, e, w)
    flare_angle = calculate_angle(h, s, e)
    lateral_flare = abs(e[0] - s[0]) 
    
    is_hammer_grip = (pinky[1] - thumb[1]) > 0.025
    
    if elbow_angle > BICEP_SETTINGS["EXTENDED"]: stage = "DOWN"
    elif elbow_angle < BICEP_SETTINGS["TARGET_FLEX"] + BICEP_SETTINGS["BUFFER"] and stage == "DOWN": stage = "UP"

    feedback, color = "READY", (255, 255, 255)
    
    if flare_angle > 25 or lateral_flare > 0.15:
        feedback, color = "TUCK ELBOWS IN", (0, 0, 255) 
    elif is_hammer_grip and elbow_angle < 130:
        feedback, color = "PALMS UP! (WRONG GRIP)", (0, 0, 255)
    elif elbow_angle > BICEP_SETTINGS["EXTENDED"] - 10:
        feedback, color = "ARMS EXTENDED", (255, 255, 255)
    elif elbow_angle > BICEP_SETTINGS["TARGET_FLEX"] + BICEP_SETTINGS["BUFFER"]:
        if stage == "DOWN":
            feedback, color = "CURL HIGHER", (0, 165, 255) 
        else:
            feedback, color = "LOWER WEIGHT SLOWLY", (0, 255, 255) 
    else:
        feedback, color = "PERFECT PEAK!", (0, 255, 0) 

    tel = [f"Elbow: {int(elbow_angle)}", f"Grip Check: {'Hammer' if is_hammer_grip else 'Bicep'}"]
    return feedback, color, stage, tel

# --- 8. HAMMER CURLS ---
def analyze_hammer_curl(landmarks, stage):
    h = [landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y]
    s = [landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y]
    e = [landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].y]
    w = [landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].y]
    
    thumb = [landmarks[mp_pose.PoseLandmark.RIGHT_THUMB.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_THUMB.value].y]
    pinky = [landmarks[mp_pose.PoseLandmark.RIGHT_PINKY.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_PINKY.value].y]
    
    elbow_angle = calculate_angle(s, e, w)
    flare_angle = calculate_angle(h, s, e)
    lateral_flare = abs(e[0] - s[0])
    
    is_bicep_grip = abs(pinky[1] - thumb[1]) < 0.015 or thumb[1] > pinky[1]
    
    if elbow_angle > HAMMER_SETTINGS["EXTENDED"]: stage = "DOWN"
    elif elbow_angle < HAMMER_SETTINGS["TARGET_FLEX"] + HAMMER_SETTINGS["BUFFER"]: stage = "UP"

    feedback, color = "READY", (255, 255, 255)
    
    if flare_angle > 35 or lateral_flare > 0.15: 
        feedback, color = "TUCK ELBOWS IN", (0, 0, 255) 
    elif is_bicep_grip and elbow_angle < 130:
        feedback, color = "USE NEUTRAL GRIP", (0, 0, 255)
    elif elbow_angle > HAMMER_SETTINGS["EXTENDED"] - 10:
        feedback, color = "ARMS EXTENDED", (255, 255, 255)
    elif elbow_angle > HAMMER_SETTINGS["TARGET_FLEX"] + HAMMER_SETTINGS["BUFFER"]:
        if stage == "DOWN":
            feedback, color = "CURL HIGHER", (0, 165, 255)
        else:
            feedback, color = "LOWER DOWN", (0, 255, 255)
    else:
        feedback, color = "PERFECT HAMMER", (0, 255, 0)

    tel = [f"Elbow: {int(elbow_angle)}", f"Grip Check: {'Bicep' if is_bicep_grip else 'Hammer'}"]
    return feedback, color, stage, tel

# --- 9. LATERAL RAISES ---
def analyze_lateral_raise(landmarks, stage):
    h = [landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y]
    s = [landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y]
    e = [landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].y]
    w = [landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].y]
    
    shoulder_angle = calculate_angle(h, s, e)
    elbow_angle = calculate_angle(s, e, w)
    
    target = LATERAL_SETTINGS["TARGET_UP"]
    buffer = LATERAL_SETTINGS["BUFFER"]
    
    if shoulder_angle < LATERAL_SETTINGS["DOWN"]: stage = "DOWN"
    elif shoulder_angle > target - buffer: stage = "UP"

    feedback, color = "READY", (255, 255, 255)
    
    if elbow_angle < LATERAL_SETTINGS["ELBOW_MIN"]:
        feedback, color = "STRAIGHTEN ARMS (TOO BENT)", (0, 0, 255)
    elif shoulder_angle > target + buffer:
        feedback, color = "TOO HIGH (LOWER ARMS)", (0, 0, 255)
    elif shoulder_angle < target - buffer:
        if stage == "DOWN":
            feedback, color = "RAISE ARMS HIGHER", (0, 165, 255)
        else:
            feedback, color = "LOWER ARMS", (0, 255, 255)
    else:
        feedback, color = "PERFECT HEIGHT", (0, 255, 0)

    tel = [f"Shoulder Raise: {int(shoulder_angle)} (Target: {int(target)})", f"Elbow Bend: {int(elbow_angle)}"]
    return feedback, color, stage, tel

# --- 10. SHOULDER PRESS ---
def analyze_shoulder_press(landmarks, stage):
    # Right Arm
    r_s = [landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y]
    r_e = [landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].y]
    r_w = [landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].y]

    # Left Arm
    l_s = [landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
    l_e = [landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].x, landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].y]
    l_w = [landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].x, landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].y]
    
    r_angle = calculate_angle(r_s, r_e, r_w)
    l_angle = calculate_angle(l_s, l_e, l_w)
    
    avg_angle = (r_angle + l_angle) / 2
    avg_wrist_y = (r_w[1] + l_w[1]) / 2
    avg_shoulder_y = (r_s[1] + l_s[1]) / 2
    
    target_ext = PRESS_SETTINGS["TARGET_EXTENSION"] - PRESS_SETTINGS["BUFFER"]
    
    
    target_start = 70 
    
    if avg_angle > target_ext: 
        stage = "UP"
    elif avg_angle <= target_start and stage == "UP": 
        stage = "DOWN"

    feedback, color = "READY", (255, 255, 255)
    
    # Priority 1: Prevent the 1-arm phone-holding paradox
    if abs(r_angle - l_angle) > 35:
        feedback, color = "UNEVEN PRESS (BALANCE ARMS)", (0, 0, 255)
        
    # Priority 2: Hands resting completely at sides (wrists physically below shoulders)
    elif avg_wrist_y > avg_shoulder_y:
        feedback, color = "RAISE WEIGHTS TO SHOULDERS", (255, 255, 255)
        
    # Priority 3: Perfect lockout at the top
    elif avg_angle > target_ext:
        feedback, color = "PERFECT PRESS!", (0, 255, 0)
        
    # Priority 4: PURE ELBOW ANGLE DEPTH CHECK (The strict fix you requested)
    elif avg_angle <= target_start:
        feedback, color = "GOOD DEPTH, PRESS UP!", (0, 255, 0)
        
    # Priority 5: The "Half-Rep" In-Between Zone
    else:
        if stage == "UP":
            feedback, color = "LOWER ALL THE WAY DOWN", (0, 165, 255)
        else:
            feedback, color = "PRESS HIGHER (LOCKOUT)", (0, 255, 255)

    tel = [f"Avg Elbow: {int(avg_angle)} (Must drop below: {int(target_start)})", f"L: {int(l_angle)} | R: {int(r_angle)}"]
    return feedback, color, stage, tel