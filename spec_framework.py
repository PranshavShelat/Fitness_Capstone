"""The declarative core: an exercise is DATA (metrics, rep phases, ordered fault
rules), and one shared evaluator runs all of them.

Why this exists: the original engine.py hand-wrote one analyzer per exercise.
At ten exercises that was ~450 lines of near-identical structure - read
landmarks, compute a couple of angles, run an if/elif ladder, format telemetry -
and any shared bug (right-side-only landmark reads, missing visibility checks)
had to be fixed in ten places. At twenty-two it would have been ~1000 more.
Here every exercise supplies only what actually differs between exercises, and
cross-cutting concerns - side selection, visibility gating, rep counting, fault
priority - are implemented once and therefore behave identically everywhere.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional

from pose_math import Landmarks, pick_side

# OpenCV BGR tuples - the web layer converts these to CSS in server.py.
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (0, 0, 255)
ORANGE = (0, 165, 255)
YELLOW = (0, 255, 255)

# --- Robustness for real webcams (see tests/test_robustness.py) ---------------
# MediaPipe always returns all 33 landmarks and GUESSES the ones it cannot see.
# These checks stop those guesses from becoming phantom reps and
# impossible angles. They are on for the app and off for the parity build
# (spec.robust = False), which must reproduce the original engine exactly.
#
# 1. Every joint an exercise COUNTS REPS WITH (spec.critical) must be seen on
#    its own - not just on average - and must be inside the picture. The old
#    mean-visibility gate let a clearly visible hip and shoulder "carry" an ankle
#    that was off-screen. Other joints (e.g. the hips during a seated press) may
#    be out of view; the existing mean gate still covers them.
JOINT_MIN_VISIBILITY = 0.25
FRAME_MARGIN = 0.03            # landmarks may sit this far outside 0..1
# ...but a joint just past the edge that MediaPipe is still confident about
# (hands above the frame at the top of a press: 0.41-0.69) is extrapolated
# reliably, so being off-frame only counts when confidence is also below this.
# Truly hidden joints (feet below a laptop camera) sit near 0.00.
OFFFRAME_MIN_VISIBILITY = 0.40
# 2. Entering the worked position (the bottom of a squat, the top of a curl)
#    only counts after it is held this many frames in a row, so one glitchy
#    frame can't start a phantom rep. Returning to the start is NOT delayed:
#    real reps often pass through the top in a single frame.
REP_CONFIRM_FRAMES = 2
# 3. Which body side is read only flips after the other side has looked better
#    for this many frames, instead of flickering frame to frame.
SIDE_SWITCH_FRAMES = 6
# 4. A rep must START from the rest position. Several specs began in their
#    worked stage, so simply standing with arms by your sides counted a rep
#    before any lift (curls, lateral raises, pull-ups), and a clip that opens at
#    the top of a hip thrust counted the first lowering as a full rep. In the
#    robust build, the worked stage can only be entered once the rest position
#    has actually been seen - except for exercises whose natural start IS the
#    worked position (spec.starts_in_work: the shoulder press begins with the
#    weights at the shoulders).

def _hidden(L, name):
    """True if MediaPipe is only guessing this joint: low visibility, or outside
    the picture."""
    v = L.v(name)
    if v < JOINT_MIN_VISIBILITY:
        return True
    off_frame = (not (-FRAME_MARGIN <= L.x(name) <= 1 + FRAME_MARGIN)
                 or not (-FRAME_MARGIN <= L.y(name) <= 1 + FRAME_MARGIN))
    return off_frame and v < OFFFRAME_MIN_VISIBILITY


def _joint_names(names):
    out = []
    for n in names:
        pretty = _PRETTY_JOINT.get(n, n.replace("_", " "))
        if pretty not in out:
            out.append(pretty)
    return out


_PRETTY_JOINT = {"ankle": "feet", "heel": "feet", "foot": "feet", "knee": "knees",
                 "hip": "hips", "shoulder": "shoulders", "elbow": "elbows", "wrist": "hands"}


@dataclass
class Rule:
    """One feedback branch. `when(M, P)` receives the frame's metrics (plus the
    current rep stage as M["_stage"]) and the exercise's calibrated parameters.

    Rules are evaluated in order and the FIRST match wins, which is what encodes
    clinical priority: a fault that risks injury must be listed above a message
    that is merely coaching depth or tempo, or it will be masked by it.
    """
    when: Callable
    message: str
    color: tuple = WHITE


@dataclass
class RepPhase:
    """Two-state rep machine.

    `rest_when` returns the athlete to the un-worked position; `work_when` moves
    them into the worked position. A rep is counted on the worked -> rest
    transition (server.py owns the counting; this only owns the state).

    require_prev=True means the worked transition only fires from the rest
    stage, which stops a rep being counted when the athlete never fully returned
    to the start. A few of the original analyzers omitted that guard; each spec
    below records which, so the migration stays behaviour-identical and the
    guard can be turned on later as a deliberate, measurable change.
    """
    rest_when: Callable
    work_when: Callable
    rest_stage: str = "UP"
    work_stage: str = "DOWN"
    require_prev: bool = True
    initial: str = "UP"


@dataclass
class ExerciseSpec:
    id: str
    name: str
    # Semantic landmark names (pose_math naming) this exercise's maths depends
    # on. Used both to pick the better-visible body side and to gate feedback.
    reads: tuple = ()
    side: str = "r"                     # "r", "l", or "auto"
    # Below this mean visibility for `reads`, the analyzer refuses to give form
    # feedback and asks the user to fix their camera instead. MediaPipe always
    # emits a full 33-point skeleton, interpolating landmarks it cannot actually
    # see - so without this gate an occluded joint produces a confident,
    # completely invented angle. Several golden recordings sit at 0.1 visibility
    # on the very joint their exercise is about; this is what stops the app
    # inventing feedback in that situation.
    min_visibility: float = 0.0
    gate_message: str = "ADJUST CAMERA - BODY NOT FULLY VISIBLE"
    metrics: dict = field(default_factory=dict)
    params: dict = field(default_factory=dict)
    rep: Optional[RepPhase] = None
    rules: list = field(default_factory=list)
    default: tuple = ("READY", WHITE)
    telemetry: list = field(default_factory=list)
    # Provenance of this exercise's thresholds: "golden" (derived from its
    # golden_dataset recording), "fallback" (recording was unusable, thresholds
    # come from documented ranges), or "mixed".
    calibration_source: str = "golden"
    # Webcam robustness checks (see the constants at the top). Off only for the
    # parity build that must match the original engine frame for frame.
    robust: bool = True
    # Joints the rep angle is built from; hidden ones pause tracking. Empty =
    # every joint in `reads`.
    critical: tuple = ()
    # True when a set naturally begins in the worked stage (see check 4).
    starts_in_work: bool = False
    calibration_notes: str = ""
    # Draft specs stay defined but are not offered in the UI or routed by the
    # server until they have been tuned and validated against their recording.
    enabled: bool = True

    def initial_state(self):
        return {"stage": self.rep.initial if self.rep else None, "vars": {}}


def analyze(spec, landmarks, state):
    """Evaluate one frame against one spec.

    Returns (feedback, color, state, telemetry). `state` is mutated in place and
    returned for convenience; callers keep one per connection per exercise.
    """
    if state is None or state.get("stage", "__missing__") == "__missing__":
        state = spec.initial_state()
    S = state.setdefault("vars", {})

    if spec.side == "auto":
        side = pick_side(landmarks, list(spec.reads))
        if spec.robust:
            current = state.get("side") or side
            if side != current:
                S["_side_votes"] = S.get("_side_votes", 0) + 1
                if S["_side_votes"] >= SIDE_SWITCH_FRAMES:
                    current, S["_side_votes"] = side, 0
            else:
                S["_side_votes"] = 0
            state["side"] = side = current
    else:
        side = spec.side
    L = Landmarks(landmarks, side)

    # --- visibility gate -------------------------------------------------
    if spec.min_visibility > 0 and spec.reads:
        seen = L.mean_visibility(list(spec.reads))
        if seen < spec.min_visibility:
            missing = sorted(spec.reads, key=lambda n: L.v(n))[:2]
            pretty = " / ".join(n.replace("_", " ") for n in missing)
            return (
                f"{spec.gate_message} ({pretty})",
                YELLOW,
                state,
                [f"Visibility: {seen:.2f} (need {spec.min_visibility:.2f})"],
            )
        if spec.robust:
            unseen = [n for n in (spec.critical or spec.reads) if _hidden(L, n)]
            if unseen:
                S["_stage_votes"] = 0   # a hidden joint never confirms a rep
                names = _joint_names(unseen)
                return (
                    f"STEP BACK - CAN'T SEE YOUR {' / '.join(names[:2]).upper()}",
                    YELLOW,
                    state,
                    [f"Not in view: {', '.join(names)}"],
                )

    # --- metrics ---------------------------------------------------------
    P = spec.params
    M = {}
    for name, fn in spec.metrics.items():
        M[name] = fn(L, M, S, P)

    # --- rep phase -------------------------------------------------------
    if spec.rep:
        stage = state.get("stage") or spec.rep.initial
        r = spec.rep
        wanted = stage
        if r.rest_when(M, P):
            wanted = r.rest_stage
            S["_seen_rest"] = True
        elif (r.work_when(M, P) and (not r.require_prev or stage == r.rest_stage)
              and (not spec.robust or spec.starts_in_work or S.get("_seen_rest"))):
            wanted = r.work_stage
        if not spec.robust:
            stage = wanted
        elif wanted != stage and wanted == r.work_stage:
            votes = S.get("_stage_votes", 0) + 1 if S.get("_stage_wanted") == wanted else 1
            S["_stage_wanted"], S["_stage_votes"] = wanted, votes
            if votes >= REP_CONFIRM_FRAMES:
                stage, S["_stage_votes"] = wanted, 0
        else:
            stage, S["_stage_votes"] = wanted, 0
        state["stage"] = stage
        M["_stage"] = stage
    else:
        M["_stage"] = None

    M["_side"] = side

    # Expose this frame's numeric metrics so the server can record the actual
    # measured value behind a fault (e.g. "knee angle 63 deg") for the report.
    state["metrics"] = {k: float(v) for k, v in M.items()
                        if not k.startswith("_") and isinstance(v, (int, float))}

    # --- ordered fault / feedback rules ----------------------------------
    feedback, color = spec.default
    for rule in spec.rules:
        if rule.when(M, P):
            feedback, color = rule.message, rule.color
            break

    # A RED fault may come from a secondary joint MediaPipe is only guessing
    # (e.g. the hip behind a desk during curls - which once produced an
    # impossible "elbow 123 deg forward"). Reps still count off the critical
    # joints, but an injury warning is never raised from a guessed joint.
    if spec.robust and spec.critical and color == RED:
        guessed = [n for n in spec.reads if n not in spec.critical and _hidden(L, n)]
        if guessed:
            names = _joint_names(guessed)
            feedback, color = f"STEP BACK - CAN'T SEE YOUR {' / '.join(names[:2]).upper()}", YELLOW

    telemetry = [t(M, P) for t in spec.telemetry]
    return feedback, color, state, telemetry
