"""Derives each exercise's angle thresholds from its golden_dataset recording -
and, critically, decides whether that recording is good enough to derive them
from at all.

The original config.py trusted every CSV unconditionally: it averaged the
extreme angles of the recording and used that as the target. That is sound when
the recording actually contains a rep filmed from an angle where the rep is
visible. Measured across all 22 recordings, several do not:

  * Deadlift.csv     - hip angle varies by only 24 degrees over the whole clip and
                       the elbows read 176-180 throughout. Filmed front-on, where
                       a hip hinge is close to invisible in 2D.
  * T bar row.csv    - elbow angle varies by 15 degrees across the entire recording;
                       the pull simply is not in the data.
  * Benchpress.csv   - mean elbow visibility 0.13 (torso occludes the arms).
  * Tricep pushdowns - mean elbow visibility 0.11, wrist 0.19.

Averaging the extremes of those still returns a number. It is just not a number
that means anything, and a form checker built on it gives confident wrong
feedback - which is worse for a user than giving none. So every derived value
passes two checks (did the joint actually MOVE, and was it actually VISIBLE)
before it is trusted; anything that fails falls back to a documented
population range and is labelled as such, so the provenance of every threshold
in the app is inspectable rather than implied.
"""
import csv
import os
from dataclasses import dataclass

import numpy as np

from pose_math import Landmarks, calculate_angle

GOLDEN_DIR = "golden_dataset"

# A joint has to sweep at least this many degrees across the recording for the
# recording to be treated as containing a real repetition of that movement.
MIN_ANGLE_RANGE = 25.0
# ...and MediaPipe has to have actually seen the joints, not interpolated them.
MIN_LANDMARK_VISIBILITY = 0.40


class CsvLandmark:
    """Duck-types a MediaPipe landmark so recorded CSV rows can be fed through
    exactly the same analyzer code as a live webcam frame."""
    __slots__ = ("x", "y", "z", "visibility")

    def __init__(self, x, y, z, v):
        self.x, self.y, self.z, self.visibility = x, y, z, v


def read_frames(csv_path):
    """Returns a list of 33-landmark frames from a golden_dataset CSV."""
    frames = []
    if not os.path.exists(csv_path):
        return frames
    with open(csv_path, "r") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            try:
                vals = [float(v) for v in row]
            except ValueError:
                continue
            if len(vals) < 132:
                continue
            frames.append([
                CsvLandmark(vals[i * 4], vals[i * 4 + 1], vals[i * 4 + 2], vals[i * 4 + 3])
                for i in range(33)
            ])
    return frames


def dominant_side(frames, names):
    """Which side of the body this recording actually shows, by mean visibility."""
    if not frames:
        return "r"
    r = np.mean([Landmarks(f, "r").mean_visibility(names) for f in frames])
    l = np.mean([Landmarks(f, "l").mean_visibility(names) for f in frames])
    return "r" if r >= l else "l"


@dataclass
class Calibration:
    """One threshold plus the evidence behind it."""
    value: float
    source: str            # "golden" or "fallback"
    reason: str
    observed_range: float = 0.0
    visibility: float = 0.0
    frames: int = 0

    def __float__(self):
        return float(self.value)


def angle_series(frames, a, b, c, side, valid=(20.0, 180.0)):
    out = []
    for f in frames:
        L = Landmarks(f, side)
        ang = calculate_angle(L.p(a), L.p(b), L.p(c))
        if valid[0] < ang < valid[1]:   # drop hard-pinned readings, which are tracking glitches
            out.append(ang)
    return out


def calibrate_angle(csv_name, a, b, c, mode, fallback, side=None,
                    min_range=MIN_ANGLE_RANGE, min_visibility=MIN_LANDMARK_VISIBILITY,
                    valid=(20.0, 180.0), plausible=None):
    """Derive a target joint angle from a golden recording, or fall back.

    mode:
      "flexion"   - the tightest angle reached (bottom of a squat, top of a curl)
      "extension" - the widest angle reached (lockout of a press)
      "static"    - the mean held angle (a plank, a V-hold)

    For flexion/extension the target is the mean of the frames within 10 degrees
    of the extreme rather than the single extreme frame, so one glitched frame
    cannot define the target.

    A robust percentile estimator (5th/95th) was measured as an alternative and
    REJECTED: for slow movements the athlete spends few frames at the endpoint,
    so a percentile systematically under-reports the range actually achieved.
    On Leg extension.csv the 95th percentile is 128 degrees where the lift
    genuinely reaches 157 - a target that would coach the user to stop 30
    degrees short of full extension every rep. A target should describe what a
    good rep REACHES, which is an extreme, not a typical value.

    `plausible` is an optional (lo, hi) anatomical window. A derived value
    outside it is clamped and labelled, which catches the case where the
    recording is visible and does move but the camera's viewpoint distorts the
    2D projection of the angle - most visibly on the bench-press family, where a
    side-on camera foreshortens the upper arm and makes the bottom of a rep read
    far more acute than the joint actually is.
    """
    path = os.path.join(GOLDEN_DIR, csv_name) if csv_name else None
    frames = read_frames(path) if path else []
    if not frames:
        return Calibration(fallback, "fallback", f"no usable recording at {csv_name}")

    # side=None means "read whichever side of the body the camera actually saw".
    # The original config.py hardcoded the RIGHT side for every extraction, which
    # is measurably the wrong half of several recordings - Squats.csv's right leg
    # sits at 0.36 mean visibility, so the shipped squat depth threshold was
    # derived from a leg MediaPipe was mostly guessing at.
    side = side or dominant_side(frames, [a, b, c])
    vis = float(np.mean([Landmarks(f, side).mean_visibility([a, b, c]) for f in frames]))
    angles = angle_series(frames, a, b, c, side, valid)

    if len(angles) < 20:
        return Calibration(fallback, "fallback", "too few clean frames", 0.0, vis, len(frames))

    observed_range = float(max(angles) - min(angles))

    if vis < min_visibility:
        return Calibration(
            fallback, "fallback",
            f"joints not visible in recording (mean visibility {vis:.2f} < {min_visibility:.2f})",
            observed_range, vis, len(frames),
        )
    if mode != "static" and observed_range < min_range:
        return Calibration(
            fallback, "fallback",
            f"joint barely moves in recording (range {observed_range:.0f} deg < {min_range:.0f} deg)",
            observed_range, vis, len(frames),
        )

    if mode == "flexion":
        lo = min(angles)
        value = float(np.mean([x for x in angles if x < lo + 10]))
    elif mode == "extension":
        hi = max(angles)
        value = float(np.mean([x for x in angles if x > hi - 10]))
    else:
        value = float(np.mean(angles))

    if plausible:
        lo_p, hi_p = plausible
        if not (lo_p <= value <= hi_p):
            clamped = min(max(value, lo_p), hi_p)
            return Calibration(
                clamped, "clamped",
                f"derived {value:.0f} deg is outside the plausible {lo_p:.0f}-{hi_p:.0f} deg "
                f"window (likely camera-angle foreshortening); clamped to {clamped:.0f}",
                observed_range, vis, len(frames),
            )

    return Calibration(value, "golden", "derived from recording", observed_range, vis, len(frames))


def measure_visibility(csv_name, names):
    """Mean visibility of a set of landmarks across a recording - used to set a
    realistic per-exercise visibility gate rather than one global guess."""
    frames = read_frames(os.path.join(GOLDEN_DIR, csv_name)) if csv_name else []
    if not frames:
        return 0.0
    side = dominant_side(frames, names)
    return float(np.mean([Landmarks(f, side).mean_visibility(names) for f in frames]))


def build_phase_reference(csv_name, phase, value, bin_size=15, min_samples=2):
    """Builds a phase-indexed (lo, hi, mean, stdev) table of what `value` looks
    like at each point in a correct rep, where `phase` locates you within the rep.

    This generalises the shoulder-press elbow-rise reference. Most "is this joint
    in the right place" questions have a different correct answer at the bottom
    of a rep than at the top, so a single flat threshold either fires constantly
    at one end of the range or never fires at all - which is exactly how the
    earlier flat elbow-depth check failed.

    phase and value are (L -> float) callables over a frame's Landmarks.
    """
    frames = read_frames(os.path.join(GOLDEN_DIR, csv_name)) if csv_name else []
    if not frames:
        return []
    side = dominant_side(frames, [])
    phases, values = [], []
    for f in frames:
        L = Landmarks(f, side)
        p = phase(L)
        if not (0 < p < 180):
            continue
        phases.append(p)
        values.append(value(L))

    table = []
    for lo in range(0, 180, bin_size):
        hi = lo + bin_size
        vals = [values[i] for i in range(len(phases)) if lo <= phases[i] < hi]
        if len(vals) >= min_samples:
            table.append((lo, hi, float(np.mean(vals)), float(np.std(vals))))
    return table


def calibration_report(specs):
    """Human-readable provenance table for every threshold in the app."""
    lines = []
    for spec in specs:
        lines.append(f"{spec.id:<12} {spec.name:<22} {spec.calibration_source:<9} {spec.calibration_notes}")
    return "\n".join(lines)
