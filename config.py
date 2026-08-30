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


# Bicep/hammer curl grip checks (comparing pinky.y - thumb.y against a
# threshold to tell a supinated vs. neutral grip) were removed entirely.
# The original 0.025 threshold had the inequality direction backwards
# (checked against golden_dataset/Barbell bicep curl.csv and Hammer
# curl.csv: real bicep-curl frames average 0.039, real hammer-curl frames
# average 0.019 - the opposite of what the old code assumed), but even
# after correcting the direction and re-deriving the threshold from real
# data, the two classes still overlap substantially (~30%+ error rate) -
# a real precision limit of this 2D proxy signal, not a bug. Removed rather
# than ship a check that flickers on correct form. This doesn't affect
# telling the two exercises apart - that's already chosen via the exercise
# picker in the UI, independent of this per-frame grip check.

# --- 10. LATERAL RAISES ---
LATERAL_TARGET = extract_golden_target('golden_dataset/Lateral raise.csv', [24, 12, 14], "extension")
SAFE_LATERAL_TARGET = min(LATERAL_TARGET - 10, 85)
LATERAL_SETTINGS = {"DOWN": 30, "TARGET_UP": SAFE_LATERAL_TARGET, "BUFFER": 15, "ELBOW_MIN": 140}

# --- 11. SHOULDER PRESS ---
PRESS_TARGET = extract_golden_target('golden_dataset/Shoulder press.csv', [12, 14, 16], "extension")
# BACK_LEAN_MAX: hip->shoulder angle from vertical (same formula as SQUAT's back_angle).
# Checked against golden_dataset/Shoulder press.csv: a correct press stays within
# 1-14 degrees of vertical for its ENTIRE range of motion (mean 3.6, stdev 1.7,
# barely correlated with elbow angle/rep phase at r=-0.11) - unlike elbow-position
# signals, torso lean doesn't naturally sweep during a good rep, so a generous
# threshold well above that clean-form max reliably flags an actual forward lean.
PRESS_SETTINGS = {"START": 90, "TARGET_EXTENSION": PRESS_TARGET, "BUFFER": 15, "BACK_LEAN_MAX": 20}

# Elbow-position checks ("too far forward" and "too far back") have gone
# through three failed designs: (1) a flat threshold on elbow depth
# (landmark.z) - fails, a correct press sweeps its whole natural range on this
# signal within a single rep; (2) a reference curve built from THIS golden
# CSV - fails, MediaPipe's z isn't comparable across different cameras/
# people, and real test screenshots scored confirmed-correct form WORSE than
# bad form; (3) a live per-session "do one calibration rep yourself" flow -
# fails differently: if the user's own calibration rep still has the
# habitual fault, the reference just learns the bad habit as normal and the
# check inverts (confirmed in testing).
#
# The only design left is a reference built OFFLINE from labeled GOOD and
# FAULT recordings of the actual user's own camera (see
# build_good_fault_elbow_reference below and record_press_sample.py for how
# to capture them) - a real decision boundary between two labeled classes,
# not a threshold guessed from one. "Too far forward" and "too far back" are
# separate, independent faults (opposite directions) - each needs its OWN
# fault recording; mixing both into one file corrupts the boundary for both
# (confirmed - some angle bins showed the fault class LESS extreme than
# good). PRESS_ELBOW_FORWARD_REFERENCE / PRESS_ELBOW_BACK_REFERENCE load
# their respective recordings if both calibration_data/press_good.csv and
# the matching fault CSV exist; otherwise that check is None and simply
# stays off (same safe default as every prior failed attempt).
PRESS_SETTINGS["ELBOW_FORWARD_MARGIN"] = 0.5
PRESS_SETTINGS["ELBOW_BACK_MARGIN"] = 0.5


def extract_elbow_rise_reference(csv_path, bin_size=15):
    """Builds an expected (shoulder.y - elbow.y) lookup, binned by elbow-bend
    angle, from a real correct press recording. Positive = elbow above
    shoulder (y grows downward in image coordinates).

    Unlike the z-depth checks above (MediaPipe's noisiest, least cross-
    camera-comparable coordinate, which is why those got disabled), this uses
    x/y - the same coordinate space BACK_LEAN_MAX and the wrist-vs-elbow
    check already use reliably across different cameras. Checked against
    golden_dataset/Shoulder press.csv: this climbs smoothly with elbow-bend
    angle from -0.24 (elbow well below shoulder, racked) to +0.22 (elbow
    above shoulder, locked out) - a real, monotonic constraint of how the arm
    elevates through a genuine press, not noise. Catches "goal post" form:
    elbows flared up and out to the sides before the press has actually
    earned that height (a lateral-raise-style motion instead of a real
    overhead press).

    A rep only passes through the mid-range angles briefly (the "dwelling"
    phases at rest and lockout are what a single recording captures the most
    frames of), so those bins end up built from as few as 4-7 frames of one
    continuous motion - not enough to estimate a real population stdev, and
    real user testing confirmed it: the 90-105 bin's stdev (0.0016, an order
    of magnitude tighter than its 0.004-0.04 neighbors) turned an ordinary
    amount of per-user variation into a false "flaring" flag. STDEV_FLOOR
    keeps any thin bin from becoming absurdly, unrealistically sensitive.
    """
    STDEV_FLOOR = 0.02

    angles, values = [], []
    try:
        with open(csv_path, 'r') as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                def pt(i):
                    return [float(row[i * 4]), float(row[i * 4 + 1])]

                r_angle = calculate_angle(pt(12), pt(14), pt(16))
                l_angle = calculate_angle(pt(11), pt(13), pt(15))
                avg_angle = (r_angle + l_angle) / 2
                if not (0 < avg_angle < 180):
                    continue
                shoulder_y = (pt(12)[1] + pt(11)[1]) / 2
                elbow_y = (pt(14)[1] + pt(13)[1]) / 2
                angles.append(avg_angle)
                values.append(shoulder_y - elbow_y)
    except FileNotFoundError:
        return []

    bins = []
    for lo in range(0, 180, bin_size):
        hi = lo + bin_size
        vals = [values[i] for i in range(len(angles)) if lo <= angles[i] < hi]
        if len(vals) >= 2:
            bins.append((lo, hi, float(np.mean(vals)), max(float(np.std(vals)), STDEV_FLOOR)))
    return bins


PRESS_ELBOW_RISE_REFERENCE = extract_elbow_rise_reference('golden_dataset/Shoulder press.csv')
# Live frames whose elbow sits more than this many reference-stdevs ABOVE the
# expected height for their phase get flagged. Checked against real user
# screenshots (avg elbow angle 23 and 43, elbow visually at shoulder height,
# i.e. ~0): both landed ~4.3-4.6 stdevs above the golden reference at that
# phase, so this comfortably separates the fault from normal variation.
PRESS_SETTINGS["ELBOW_RISE_STDEV_MAX"] = 3.0


def _read_press_angle_z_samples(path):
    """Each row -> (avg_elbow_bend_angle, elbow.z - shoulder.z), same raw
    positional indexing as extract_golden_target (row[landmark_idx*4 + field])."""
    samples = []
    with open(path, 'r') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            def pt(i):
                return [float(row[i * 4]), float(row[i * 4 + 1])]

            def z(i):
                return float(row[i * 4 + 2])

            r_angle = calculate_angle(pt(12), pt(14), pt(16))
            l_angle = calculate_angle(pt(11), pt(13), pt(15))
            avg_angle = (r_angle + l_angle) / 2
            if not (0 < avg_angle < 180):
                continue
            elbow_z_rel = ((z(13) - z(11)) + (z(14) - z(12))) / 2
            samples.append((avg_angle, elbow_z_rel))
    return samples


def build_good_fault_elbow_reference(good_samples, fault_samples, direction, bin_size=15):
    """Bins two sets of (angle, elbow_z_rel_shoulder) samples - one recording
    of genuinely correct form, one of a single specific elbow-position fault -
    both from the SAME camera/person, into a per-angle decision boundary.

    direction: 'forward' if the fault's elbow.z is expected MORE NEGATIVE
    than good's (elbow closer to camera than a correct press ever gets), or
    'back' if it's expected LESS NEGATIVE/more positive (elbow further from
    camera than a correct press ever gets) - the two faults are opposite
    directions from the same good baseline, so this is shared logic with the
    comparison direction flipped.

    Per angle bin, the flagging cutoff is the midpoint between the two
    classes' means, so it's not dependent on getting a single "trust me,
    this rep is correct" sample right. Bins where the two classes don't
    separate meaningfully (or don't have enough samples) are skipped rather
    than guessed.
    """
    bins = []
    for lo in range(0, 180, bin_size):
        hi = lo + bin_size
        good_vals = [z for angle, z in good_samples if lo <= angle < hi]
        fault_vals = [z for angle, z in fault_samples if lo <= angle < hi]
        if len(good_vals) < 2 or len(fault_vals) < 2:
            continue
        good_mean = float(np.mean(good_vals))
        fault_mean = float(np.mean(fault_vals))
        gap = (good_mean - fault_mean) if direction == 'forward' else (fault_mean - good_mean)
        if gap < 0.03:
            continue
        midpoint = (good_mean + fault_mean) / 2
        bins.append((lo, hi, midpoint, gap / 2))
    return bins


def load_press_elbow_reference(good_path, fault_path, direction):
    try:
        good_samples = _read_press_angle_z_samples(good_path)
        fault_samples = _read_press_angle_z_samples(fault_path)
    except FileNotFoundError:
        return None
    return build_good_fault_elbow_reference(good_samples, fault_samples, direction) or None


# DISABLED (explicit decision): tested against real good/forward recordings
# from the user's own camera (calibration_data/press_good.csv,
# press_forward.csv) and found the false-positive rate on genuinely correct
# form was 12-19% with streaks up to 23 frames - well past FAULT_MIN_STREAK's
# 5-frame debounce in server.py. Smoothing (EMA, same technique as SQUAT's
# back_angle) and margin-tuning (0.5 through 3.0) didn't fix it: the real
# rep-to-rep variability within this user's own correct reps is comparable in
# size to the actual good-vs-fault difference, so MediaPipe's landmark.z
# doesn't carry a clean enough signal for this fault via a single monocular
# webcam - not a tuning problem. Left off rather than shipping a check that
# misfires on correct form. The loading/building functions above still work
# if ever revisited with a larger, cleaner dataset:
#   PRESS_ELBOW_FORWARD_REFERENCE = load_press_elbow_reference(
#       'calibration_data/press_good.csv', 'calibration_data/press_forward.csv', 'forward')
#   PRESS_ELBOW_BACK_REFERENCE = load_press_elbow_reference(
#       'calibration_data/press_good.csv', 'calibration_data/press_back.csv', 'back')
PRESS_ELBOW_FORWARD_REFERENCE = None
PRESS_ELBOW_BACK_REFERENCE = None