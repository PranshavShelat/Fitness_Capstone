import mediapipe as mp
import numpy as np
from utils import calculate_angle
from config import (
    SQUAT_SETTINGS, PLANK_SETTINGS, DIP_SETTINGS,
    PUSHUP_SETTINGS, PULLUP_SETTINGS, TWIST_SETTINGS,
    BICEP_SETTINGS, HAMMER_SETTINGS, LATERAL_SETTINGS, PRESS_SETTINGS,
    PRESS_ELBOW_RISE_REFERENCE
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

    elbow_angle = calculate_angle(s, e, w)
    flare_angle = calculate_angle(h, s, e)
    lateral_flare = abs(e[0] - s[0])

    if elbow_angle > BICEP_SETTINGS["EXTENDED"]: stage = "DOWN"
    elif elbow_angle < BICEP_SETTINGS["TARGET_FLEX"] + BICEP_SETTINGS["BUFFER"] and stage == "DOWN": stage = "UP"

    feedback, color = "READY", (255, 255, 255)

    if flare_angle > 25 or lateral_flare > 0.15:
        feedback, color = "TUCK ELBOWS IN", (0, 0, 255)
    elif elbow_angle > BICEP_SETTINGS["EXTENDED"] - 10:
        feedback, color = "ARMS EXTENDED", (255, 255, 255)
    elif elbow_angle > BICEP_SETTINGS["TARGET_FLEX"] + BICEP_SETTINGS["BUFFER"]:
        if stage == "DOWN":
            feedback, color = "CURL HIGHER", (0, 165, 255)
        else:
            feedback, color = "LOWER WEIGHT SLOWLY", (0, 255, 255)
    else:
        feedback, color = "PERFECT PEAK!", (0, 255, 0)

    tel = [f"Elbow: {int(elbow_angle)}"]
    return feedback, color, stage, tel

# --- 8. HAMMER CURLS ---
def analyze_hammer_curl(landmarks, stage):
    h = [landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y]
    s = [landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y]
    e = [landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].y]
    w = [landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].y]

    elbow_angle = calculate_angle(s, e, w)
    flare_angle = calculate_angle(h, s, e)
    lateral_flare = abs(e[0] - s[0])

    if elbow_angle > HAMMER_SETTINGS["EXTENDED"]: stage = "DOWN"
    elif elbow_angle < HAMMER_SETTINGS["TARGET_FLEX"] + HAMMER_SETTINGS["BUFFER"]: stage = "UP"

    feedback, color = "READY", (255, 255, 255)

    if flare_angle > 35 or lateral_flare > 0.15:
        feedback, color = "TUCK ELBOWS IN", (0, 0, 255)
    elif elbow_angle > HAMMER_SETTINGS["EXTENDED"] - 10:
        feedback, color = "ARMS EXTENDED", (255, 255, 255)
    elif elbow_angle > HAMMER_SETTINGS["TARGET_FLEX"] + HAMMER_SETTINGS["BUFFER"]:
        if stage == "DOWN":
            feedback, color = "CURL HIGHER", (0, 165, 255)
        else:
            feedback, color = "LOWER DOWN", (0, 255, 255)
    else:
        feedback, color = "PERFECT HAMMER", (0, 255, 0)

    tel = [f"Elbow: {int(elbow_angle)}"]
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

def press_elbow_forward_signal(landmarks):
    """(avg_elbow_bend_angle, elbow.z - shoulder.z) for a shoulder press frame.

    Used by record_press_sample.py to show live feedback while recording a
    calibration sample. The actual reference used at runtime is built offline
    from those recordings by config.py's load_press_elbow_reference (kept out
    of this module to avoid a config.py <-> engine.py import cycle).
    """
    r_s_lm = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value]
    r_e_lm = landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value]
    r_w_lm = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value]
    l_s_lm = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value]
    l_e_lm = landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value]
    l_w_lm = landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value]

    r_angle = calculate_angle([r_s_lm.x, r_s_lm.y], [r_e_lm.x, r_e_lm.y], [r_w_lm.x, r_w_lm.y])
    l_angle = calculate_angle([l_s_lm.x, l_s_lm.y], [l_e_lm.x, l_e_lm.y], [l_w_lm.x, l_w_lm.y])
    avg_angle = (r_angle + l_angle) / 2

    elbow_z_rel_shoulder = ((l_e_lm.z - l_s_lm.z) + (r_e_lm.z - r_s_lm.z)) / 2
    return avg_angle, elbow_z_rel_shoulder


def analyze_shoulder_press(landmarks, stage, elbow_forward_reference=None, elbow_back_reference=None):
    # Right Arm
    r_s_lm = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value]
    r_e_lm = landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value]
    r_w_lm = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value]
    r_s = [r_s_lm.x, r_s_lm.y]
    r_e = [r_e_lm.x, r_e_lm.y]
    r_w = [r_w_lm.x, r_w_lm.y]

    # Left Arm
    l_s_lm = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value]
    l_e_lm = landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value]
    l_w_lm = landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value]
    l_s = [l_s_lm.x, l_s_lm.y]
    l_e = [l_e_lm.x, l_e_lm.y]
    l_w = [l_w_lm.x, l_w_lm.y]

    # Hips - only used for torso-lean (back_angle) below, not the elbow/wrist math above.
    r_h = [landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y]
    l_h = [landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].x, landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y]

    r_angle = calculate_angle(r_s, r_e, r_w)
    l_angle = calculate_angle(l_s, l_e, l_w)

    avg_angle = (r_angle + l_angle) / 2
    avg_wrist_y = (r_w[1] + l_w[1]) / 2
    avg_elbow_y = (r_e[1] + l_e[1]) / 2
    avg_shoulder_y = (r_s[1] + l_s[1]) / 2

    # Torso lean - hip->shoulder angle from vertical, same formula as SQUAT's back_angle.
    # This is what actually catches "shoulders coming forward": unlike elbow position,
    # it's stable (1-14 degrees) across an ENTIRE correct rep (validated against
    # golden_dataset/Shoulder press.csv), so a real forward lean stands out cleanly
    # instead of being confused with normal arm motion.
    hip_mid = [(r_h[0] + l_h[0]) / 2, (r_h[1] + l_h[1]) / 2]
    shoulder_mid = [(r_s[0] + l_s[0]) / 2, (r_s[1] + l_s[1]) / 2]
    dy, dx = hip_mid[1] - shoulder_mid[1], hip_mid[0] - shoulder_mid[0]
    back_angle = abs(np.arctan2(dx, dy) * 180.0 / np.pi)

    # Elbows drifting forward or back - see press_elbow_forward_signal/
    # config.py's build_good_fault_elbow_reference for the full history: a flat
    # threshold, a reference from someone else's camera, and a live per-session
    # "calibrate yourself" flow were all tried and failed for different reasons.
    # elbow_forward_reference/elbow_back_reference here are per-angle
    # (midpoint, half_gap) decision boundaries built OFFLINE from labeled good +
    # fault recordings of this same user's own camera (config.py's
    # PRESS_ELBOW_FORWARD_REFERENCE / PRESS_ELBOW_BACK_REFERENCE) - None (no
    # recordings yet) simply skips that check rather than guessing.
    elbow_z_rel_shoulder = ((l_e_lm.z - l_s_lm.z) + (r_e_lm.z - r_s_lm.z)) / 2

    elbows_forward = False
    if elbow_forward_reference:
        for lo, hi, midpoint, half_gap in elbow_forward_reference:
            if lo <= avg_angle < hi and half_gap > 0:
                elbows_forward = (midpoint - elbow_z_rel_shoulder) / half_gap > PRESS_SETTINGS["ELBOW_FORWARD_MARGIN"]
                break

    elbows_back = False
    if elbow_back_reference:
        for lo, hi, midpoint, half_gap in elbow_back_reference:
            if lo <= avg_angle < hi and half_gap > 0:
                elbows_back = (elbow_z_rel_shoulder - midpoint) / half_gap > PRESS_SETTINGS["ELBOW_BACK_MARGIN"]
                break

    # wrist.y vs elbow.y IS phase-invariant, though: checked against the same golden
    # dataset, the wrist stays above the elbow (wrist_y - elbow_y is negative) on
    # every single one of 204 frames of a real correct press (mean -0.26, and even
    # the closest frame was still -0.07) - the arm should point generally upward
    # throughout the whole movement. A "chicken wing" position (elbows flared up,
    # forearms hanging down) inverts this regardless of what the elbow bend angle
    # measures, which is why the depth check alone missed it.
    wrist_below_elbow = (avg_wrist_y - avg_elbow_y) > -0.03

    target_ext = PRESS_SETTINGS["TARGET_EXTENSION"] - PRESS_SETTINGS["BUFFER"]

    # "Goal post" fault: elbows flared up and out to the sides before the press
    # has actually earned that height (more of a lateral raise than a real
    # overhead press) - unlike the z-depth checks above, this uses x/y
    # (shoulder.y - elbow.y), which climbs smoothly and TIGHTLY with elbow-bend
    # angle in real correct-form data (config.py's PRESS_ELBOW_RISE_REFERENCE,
    # built straight from golden_dataset/Shoulder press.csv - no per-user
    # calibration needed, same as BACK_LEAN_MAX and the wrist-vs-elbow check).
    #
    # Only applies before the press has reached full extension (avg_angle < target_ext):
    # once extension IS achieved, "did the elbows rise before earning it" is no longer
    # a coherent question - real user testing showed this firing at avg_angle ~169 (a
    # near-complete lockout) and blocking "PERFECT PRESS!" from ever showing, which
    # contradicts what the check is even meant to catch.
    elbow_above_shoulder = avg_shoulder_y - avg_elbow_y
    elbows_flared_up = False
    if avg_angle < target_ext:
        for lo, hi, ref_mean, ref_stdev in PRESS_ELBOW_RISE_REFERENCE:
            if lo <= avg_angle < hi and ref_stdev > 0:
                elbows_flared_up = (elbow_above_shoulder - ref_mean) / ref_stdev > PRESS_SETTINGS["ELBOW_RISE_STDEV_MAX"]
                break

    target_start = 70

    if avg_angle > target_ext:
        stage = "UP"
    elif avg_angle <= target_start and stage == "UP":
        stage = "DOWN"

    feedback, color = "READY", (255, 255, 255)

    # Priority 1: Hands resting completely at sides (wrists physically below shoulders) -
    # checked first since both this and "wrist below elbow" are naturally true at rest,
    # and resting is the more specific/useful message in that case.
    if avg_wrist_y > avg_shoulder_y:
        feedback, color = "RAISE WEIGHTS TO SHOULDERS", (255, 255, 255)

    # Priority 2: Torso leaning forward (shoulders drifting in front of the hips) -
    # checked before the depth/lockout messages below so leaning can't hide behind
    # an otherwise-correct elbow angle at any point in the rep.
    elif back_angle > PRESS_SETTINGS["BACK_LEAN_MAX"]:
        feedback, color = "KEEP TORSO UPRIGHT (DON'T LEAN)", (0, 0, 255)

    # Priority 3: "Chicken wing" / inverted arm position - see note above.
    elif wrist_below_elbow:
        feedback, color = "KEEP WRISTS ABOVE ELBOWS", (0, 0, 255)

    # Priority 4: Elbows drifting forward of this user's own calibrated
    # reference for this point in the rep - see note above. Silently never
    # fires until elbow_forward_reference has been calibrated.
    elif elbows_forward:
        feedback, color = "ELBOWS TOO FAR FORWARD (ROTATE BACK)", (0, 0, 255)

    # Priority 5: Elbows drifting too far BACK of this user's own calibrated
    # reference - the opposite fault, same idea, silently never fires until
    # elbow_back_reference has been calibrated.
    elif elbows_back:
        feedback, color = "ELBOWS TOO FAR BACK (BRING FORWARD SLIGHTLY)", (0, 0, 255)

    # Priority 6: "Goal post" / lateral-raise-style press - elbows flared up and
    # out ahead of where a real press would have raised them yet - see note above.
    elif elbows_flared_up:
        feedback, color = "DON'T FLARE ELBOWS (PRESS STRAIGHT UP)", (0, 0, 255)

    # Priority 7: Prevent the 1-arm phone-holding paradox. Threshold is intentionally
    # generous (55 degrees) - a single 2D webcam is very sensitive to camera angle, so
    # normal (non-uneven) presses can easily show a real 20-30 degree L/R gap just from
    # not standing perfectly square to the camera. A tighter threshold false-triggers
    # on essentially every rep regardless of actual form.
    elif abs(r_angle - l_angle) > 55:
        feedback, color = "UNEVEN PRESS (BALANCE ARMS)", (0, 0, 255)

    # Priority 8: Perfect lockout at the top
    elif avg_angle > target_ext:
        feedback, color = "PERFECT PRESS!", (0, 255, 0)

    # Priority 9: PURE ELBOW ANGLE DEPTH CHECK (The strict fix you requested)
    elif avg_angle <= target_start:
        feedback, color = "GOOD DEPTH, PRESS UP!", (0, 255, 0)

    # Priority 10: The "Half-Rep" In-Between Zone
    else:
        if stage == "UP":
            feedback, color = "LOWER ALL THE WAY DOWN", (0, 165, 255)
        else:
            feedback, color = "PRESS HIGHER (LOCKOUT)", (0, 255, 255)

    tel = [f"Avg Elbow: {int(avg_angle)} (Must drop below: {int(target_start)})", f"L: {int(l_angle)} | R: {int(r_angle)}", f"Back Lean: {int(back_angle)} (Max: {int(PRESS_SETTINGS['BACK_LEAN_MAX'])})"]
    return feedback, color, stage, tel