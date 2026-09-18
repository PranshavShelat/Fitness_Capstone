"""Public entry point for form analysis.

Everything that used to live here as ten hand-written analyzers now lives as
data in exercise_specs.py, evaluated by spec_framework.analyze(). This module is
just the front door: it builds the enabled specs once at import, and gives the
desktop app (main.py) and the web server (server.py) one identical way to
analyze a frame.

The original per-exercise functions are preserved unchanged in
tests/legacy/engine_legacy.py, where the parity test replays every golden
recording through both implementations and asserts they agree frame for frame.
"""
from exercise_specs import build_specs
from pose_math import Landmarks, calculate_angle
from spec_framework import analyze as _analyze

# Built once at import - calibration reads the golden recordings off disk, so it
# should not happen per frame or per connection.
ALL_SPECS = build_specs()
SPECS = {k: v for k, v in ALL_SPECS.items() if v.enabled}

# What the UI offers, in the order it offers it.
EXERCISES = [{"id": s.id, "name": s.name} for s in SPECS.values()]

# mode -> (worked_stage, rest_stage); a rep completes on worked -> rest.
# Derived from the specs rather than maintained as a second hand-written list,
# so a new exercise cannot be added with its rep counting silently missing.
REP_TRANSITIONS = {
    k: (s.rep.work_stage, s.rep.rest_stage) for k, s in SPECS.items() if s.rep
}

HOLD_MODES = tuple(k for k, s in SPECS.items() if s.rep is None)


def new_state(mode):
    spec = SPECS.get(mode)
    return spec.initial_state() if spec else None


def analyze_frame(mode, landmarks, state=None):
    """Analyze one frame. Returns (feedback, bgr_color, state, telemetry).

    An unknown mode returns a neutral message rather than raising, so a stale or
    mistyped client request cannot take the server down mid-workout.
    """
    spec = SPECS.get(mode)
    if spec is None:
        return "UNKNOWN EXERCISE", (255, 255, 255), state, []
    return _analyze(spec, landmarks, state)


def press_elbow_forward_signal(landmarks):
    """(avg elbow bend angle, elbow.z - shoulder.z) for a shoulder-press frame.

    Kept for record_press_sample.py, the offline calibration recorder. See the
    notes in config.py for why the checks built on this signal ship disabled.
    """
    L = Landmarks(landmarks, "r")
    r = calculate_angle(L.p("r_shoulder"), L.p("r_elbow"), L.p("r_wrist"))
    l = calculate_angle(L.p("l_shoulder"), L.p("l_elbow"), L.p("l_wrist"))
    elbow_z_rel_shoulder = ((L.z("l_elbow") - L.z("l_shoulder"))
                            + (L.z("r_elbow") - L.z("r_shoulder"))) / 2
    return (r + l) / 2, elbow_z_rel_shoulder
