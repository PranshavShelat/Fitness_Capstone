"""Pose geometry primitives shared by every exercise analyzer.

Deliberately free of any I/O, audio or MediaPipe-runtime imports so the whole
form-checking layer can be unit-tested and replayed against recorded CSVs
headlessly (utils.py pulls in gTTS/playsound, which a server or a test runner
has no business requiring).

Landmark indices follow the MediaPipe Pose 33-point topology, which is also the
column order of every golden_dataset/*.csv (x,y,z,visibility per landmark).
"""
import numpy as np

# --- MediaPipe Pose landmark indices, by semantic name ---
LANDMARK_INDEX = {
    "nose": 0,
    "l_eye_inner": 1, "l_eye": 2, "l_eye_outer": 3,
    "r_eye_inner": 4, "r_eye": 5, "r_eye_outer": 6,
    "l_ear": 7, "r_ear": 8,
    "mouth_l": 9, "mouth_r": 10,
    "l_shoulder": 11, "r_shoulder": 12,
    "l_elbow": 13, "r_elbow": 14,
    "l_wrist": 15, "r_wrist": 16,
    "l_pinky": 17, "r_pinky": 18,
    "l_index": 19, "r_index": 20,
    "l_thumb": 21, "r_thumb": 22,
    "l_hip": 23, "r_hip": 24,
    "l_knee": 25, "r_knee": 26,
    "l_ankle": 27, "r_ankle": 28,
    "l_heel": 29, "r_heel": 30,
    "l_foot": 31, "r_foot": 32,
}

# Landmarks that exist as a left/right pair, addressable unsided (e.g. "elbow")
# and resolved against whichever side a spec is reading.
SIDED = {
    "shoulder", "elbow", "wrist", "hip", "knee", "ankle",
    "heel", "foot", "pinky", "index", "thumb", "ear", "eye",
}


def calculate_angle(a, b, c):
    """Interior angle ABC in degrees, 0-180, from 2D points."""
    a, b, c = np.array(a), np.array(b), np.array(c)
    radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(a[1] - b[1], a[0] - b[0])
    angle = np.abs(radians * 180.0 / np.pi)
    if angle > 180.0:
        angle = 360 - angle
    return angle


def segment_lean(a, b):
    """Angle in degrees between the segment a->b and vertical (0 = perfectly
    vertical). Sign-free. Same formula the original squat back-angle used:
    atan2(dx, dy) with dy the dominant axis, so it measures deviation FROM
    vertical rather than from horizontal.
    """
    dy, dx = a[1] - b[1], a[0] - b[0]
    return float(abs(np.arctan2(dx, dy) * 180.0 / np.pi))


class Landmarks:
    """Reads one frame of pose landmarks by semantic name, resolving unsided
    names ("elbow") against the side this frame is being read from.

    Accepts anything with .x/.y/.z/.visibility attributes - MediaPipe's own
    landmark objects, server.py's MockLandmark, or the CSV replay shim in
    tests - so the identical analyzer code runs live and offline.
    """

    __slots__ = ("_lm", "side")

    def __init__(self, landmarks, side="r"):
        self._lm = landmarks
        self.side = side  # "r" or "l"

    def _resolve(self, name):
        if name in SIDED:
            name = f"{self.side}_{name}"
        return LANDMARK_INDEX[name]

    def raw(self, name):
        return self._lm[self._resolve(name)]

    def p(self, name):
        lm = self.raw(name)
        return [lm.x, lm.y]

    def x(self, name):
        return self.raw(name).x

    def y(self, name):
        return self.raw(name).y

    def z(self, name):
        return self.raw(name).z

    def v(self, name):
        return getattr(self.raw(name), "visibility", 1.0)

    def mean_visibility(self, names):
        if not names:
            return 1.0
        return float(np.mean([self.v(n) for n in names]))


def pick_side(landmarks, names, default="r"):
    """Chooses which body side to read for this frame, by mean visibility of the
    landmarks the spec actually needs.

    The original analyzers hardcoded the RIGHT side, which silently produced
    wrong angles whenever a user happened to stand with their left side to the
    camera - the occluded limb's landmarks are still *emitted* by MediaPipe
    (interpolated), just with low visibility, so nothing errored, the numbers
    were simply wrong. Choosing per frame by visibility fixes that without
    asking the user to stand a particular way.
    """
    right = Landmarks(landmarks, "r").mean_visibility(names)
    left = Landmarks(landmarks, "l").mean_visibility(names)
    if abs(right - left) < 0.05:
        return default
    return "r" if right > left else "l"


# --------------------------------------------------------------------------
# Metric factories. Each returns fn(L, M, S, P) -> float, where
#   L = Landmarks for this frame
#   M = metrics already computed this frame (so metrics can build on metrics)
#   S = per-session mutable state (for smoothing / history)
#   P = this exercise's calibrated parameters
# --------------------------------------------------------------------------

def angle(a, b, c):
    """Joint angle at b, between segments b->a and b->c."""
    return lambda L, M, S, P: calculate_angle(L.p(a), L.p(b), L.p(c))


def bilateral_angle(a, b, c):
    """Mean of the same joint angle measured on both sides. For movements that
    are inherently two-limbed (overhead press, bench press) where one arm
    lagging is itself the signal, not noise to be discarded.
    """
    def fn(L, M, S, P):
        r = calculate_angle(L.p(f"r_{a}"), L.p(f"r_{b}"), L.p(f"r_{c}"))
        l = calculate_angle(L.p(f"l_{a}"), L.p(f"l_{b}"), L.p(f"l_{c}"))
        return (r + l) / 2
    return fn


def side_angle(side, a, b, c):
    return lambda L, M, S, P: calculate_angle(
        L.p(f"{side}_{a}"), L.p(f"{side}_{b}"), L.p(f"{side}_{c}")
    )


def lean(a, b):
    """Degrees the segment a->b deviates from vertical."""
    return lambda L, M, S, P: segment_lean(L.p(a), L.p(b))


def midpoint_lean(a, b):
    """Same as lean() but between the midpoints of the left/right pairs of two
    landmark names - a torso lean measured from both hips to both shoulders is
    far steadier than one measured down a single side.
    """
    def fn(L, M, S, P):
        pa = [(L.x(f"r_{a}") + L.x(f"l_{a}")) / 2, (L.y(f"r_{a}") + L.y(f"l_{a}")) / 2]
        pb = [(L.x(f"r_{b}") + L.x(f"l_{b}")) / 2, (L.y(f"r_{b}") + L.y(f"l_{b}")) / 2]
        return segment_lean(pa, pb)
    return fn


def y_diff(a, b):
    """a.y - b.y. Image coordinates: y grows DOWNWARD, so a positive result
    means a sits lower on screen than b."""
    return lambda L, M, S, P: L.y(a) - L.y(b)


def x_gap(a, b):
    return lambda L, M, S, P: abs(L.x(a) - L.x(b))


def bilateral_y_diff(a, b):
    """Mean y of the a-pair minus mean y of the b-pair."""
    def fn(L, M, S, P):
        ya = (L.y(f"r_{a}") + L.y(f"l_{a}")) / 2
        yb = (L.y(f"r_{b}") + L.y(f"l_{b}")) / 2
        return ya - yb
    return fn


def z_diff(a, b):
    return lambda L, M, S, P: L.z(a) - L.z(b)


def width_ratio(inner_a, inner_b, outer_a, outer_b):
    """Horizontal span of one landmark pair as a fraction of another's - e.g.
    knee width over hip width, which detects knee valgus without depending on
    how far the user is standing from the camera.
    Returns None-safe 1.0 when the reference span is too small to divide by.
    """
    def fn(L, M, S, P):
        outer = abs(L.x(outer_a) - L.x(outer_b))
        inner = abs(L.x(inner_a) - L.x(inner_b))
        if outer < 1e-6:
            return 1.0
        return inner / outer
    return fn


def asymmetry(a, b, c):
    """Absolute left/right difference of the same joint angle."""
    def fn(L, M, S, P):
        r = calculate_angle(L.p(f"r_{a}"), L.p(f"r_{b}"), L.p(f"r_{c}"))
        l = calculate_angle(L.p(f"l_{a}"), L.p(f"l_{b}"), L.p(f"l_{c}"))
        return abs(r - l)
    return fn


def visibility(*names):
    return lambda L, M, S, P: L.mean_visibility(list(names))


def smoothed(key, inner, alpha=0.8):
    """Exponential moving average of another metric, persisted in session state.
    new = alpha*previous + (1-alpha)*raw, matching the original squat back-angle
    smoothing exactly (alpha 0.8).
    """
    def fn(L, M, S, P):
        raw = inner(L, M, S, P)
        prev = S.get(key, 0.0)
        value = alpha * prev + (1 - alpha) * raw
        S[key] = value
        return value
    return fn


def derived(fn_of_metrics):
    """A metric computed purely from metrics already in M."""
    return lambda L, M, S, P: fn_of_metrics(M, P)


def binned_deviation(metric_key, phase_key, reference_key):
    """How many reference-standard-deviations `metric_key` sits ABOVE the value
    a correct rep shows at this point in the movement.

    `reference_key` names a table of (phase_lo, phase_hi, mean, stdev) rows in P,
    built offline from a correct-form recording and looked up by `phase_key`
    (usually the joint angle that defines where in the rep we are). This is the
    generalisation of the shoulder-press elbow-rise check: a threshold that
    MOVES with the rep phase, because almost every "is this joint in the right
    place" question has a different correct answer at the bottom of a rep than
    at the top.

    Returns 0.0 when no reference row covers the current phase, so an
    uncalibrated or out-of-range frame never fires a fault.
    """
    def fn(L, M, S, P):
        table = P.get(reference_key) or []
        phase = M[phase_key]
        value = M[metric_key]
        for lo, hi, mean, stdev in table:
            if lo <= phase < hi and stdev > 0:
                return (value - mean) / stdev
        return 0.0
    return fn


def running_extreme(key, metric_key, kind="max", decay=0.995):
    """A slowly-decaying running max (or min) of another metric, used as a
    session baseline for "has this drifted from where it started" checks.

    Some faults are not about an absolute angle at all - they are about a joint
    LEAVING a position it is supposed to hold. A T-bar row torso creeping
    upright, or hips peeling off a leg-extension seat, look perfectly normal on
    any single frame; only the drift is the fault. A plain average would absorb
    the drift and stop flagging it, so this tracks the extreme instead and lets
    it decay back only slowly, meaning a genuine sustained change eventually
    re-baselines while a rep-by-rep cheat keeps getting caught.
    """
    def fn(L, M, S, P):
        value = M[metric_key]
        prev = S.get(key)
        if prev is None:
            current = value
        elif (kind == "max" and value > prev) or (kind == "min" and value < prev):
            current = value
        else:
            current = prev + (value - prev) * (1 - decay)
        S[key] = current
        return current
    return fn


def delta(key, metric_key):
    """Frame-to-frame change in another metric (0 on the first frame)."""
    def fn(L, M, S, P):
        value = M[metric_key]
        prev = S.get(key, value)
        S[key] = value
        return value - prev
    return fn


def gap(metric_key, baseline_key):
    """baseline - current, for drift checks built on running_extreme."""
    return lambda L, M, S, P: M[baseline_key] - M[metric_key]
