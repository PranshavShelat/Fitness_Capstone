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

    side = pick_side(landmarks, list(spec.reads)) if spec.side == "auto" else spec.side
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

    # --- metrics ---------------------------------------------------------
    P = spec.params
    M = {}
    for name, fn in spec.metrics.items():
        M[name] = fn(L, M, S, P)

    # --- rep phase -------------------------------------------------------
    if spec.rep:
        stage = state.get("stage") or spec.rep.initial
        r = spec.rep
        if r.rest_when(M, P):
            stage = r.rest_stage
        elif r.work_when(M, P) and (not r.require_prev or stage == r.rest_stage):
            stage = r.work_stage
        state["stage"] = stage
        M["_stage"] = stage
    else:
        M["_stage"] = None

    M["_side"] = side

    # --- ordered fault / feedback rules ----------------------------------
    feedback, color = spec.default
    for rule in spec.rules:
        if rule.when(M, P):
            feedback, color = rule.message, rule.color
            break

    telemetry = [t(M, P) for t in spec.telemetry]
    return feedback, color, state, telemetry
