"""Proves the declarative rewrite is behaviour-identical to the original engine.

Every one of the 22 golden recordings is replayed through every one of the 10
original analyzers AND through the equivalent spec, frame by frame, asserting
the feedback string, colour, rep stage and telemetry lines all match exactly.

Cross-feeding every recording through every analyzer (not just its own) is
deliberate: a squat recording pushed through the shoulder-press analyzer drives
the rule ladder into branches its own recording never reaches, so the test
covers the fault priority ordering rather than just the happy path.

The reference implementation is frozen in tests/legacy/ - it is the ORIGINAL
engine.py and config.py, untouched.
"""
import glob
import os
import sys
import types

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.chdir(REPO)

from pose_math import calculate_angle  # noqa: E402

# The frozen original config.py imports calculate_angle from utils.py, which
# pulls in gTTS/playsound at module scope. Stub it so the reference engine can
# be imported in a headless test runner - the maths is identical either way.
_stub = types.ModuleType("utils")
_stub.calculate_angle = calculate_angle
_stub.speak = lambda *a, **k: None
sys.modules.setdefault("utils", _stub)

# The frozen original engine reaches landmark indices through
# mediapipe.solutions.pose.PoseLandmark. Stub that enum from pose_math's index
# table so the reference runs headlessly - and note that the NEW engine needs no
# such stub, because it no longer imports mediapipe at all.
class _Enum:
    def __init__(self, value):
        self.value = value


class _PoseLandmark:
    pass


from pose_math import LANDMARK_INDEX  # noqa: E402

_ALIAS = {"l": "LEFT", "r": "RIGHT"}
for _name, _idx in LANDMARK_INDEX.items():
    _parts = _name.split("_")
    if _parts[0] in _ALIAS:
        _upper = f"{_ALIAS[_parts[0]]}_{'_'.join(_parts[1:]).upper()}"
    else:
        _upper = _name.upper()
    setattr(_PoseLandmark, _upper, _Enum(_idx))

_mp = types.ModuleType("mediapipe")
_mp.solutions = types.SimpleNamespace(pose=types.SimpleNamespace(PoseLandmark=_PoseLandmark))
sys.modules["mediapipe"] = _mp

sys.path.insert(0, os.path.join(REPO, "tests", "legacy"))
import config_legacy                                    # noqa: E402
sys.modules["config"] = config_legacy
import engine_legacy as legacy                          # noqa: E402

from calibration import read_frames                     # noqa: E402
from exercise_specs import build_specs                  # noqa: E402
from spec_framework import analyze                      # noqa: E402


LEGACY_MODES = ("SQUAT", "PLANK", "DIP", "PUSHUP", "PULLUP", "TWIST",
                "BICEP", "HAMMER", "LATERAL", "PRESS")


def legacy_runner(mode):
    """Adapts each original analyzer to one uniform (frame -> result) closure,
    carrying whatever per-exercise state that analyzer needed."""
    state = {"stage": "UP", "back": 0}

    def run(lms):
        if mode == "SQUAT":
            fb, c, state["stage"], state["back"], tel = legacy.analyze_squat(
                lms, state["stage"], state["back"])
        elif mode == "PLANK":
            fb, c, tel = legacy.analyze_plank(lms)
        elif mode == "DIP":
            fb, c, state["stage"], tel = legacy.analyze_tricep_dip(lms, state["stage"])
        elif mode == "PUSHUP":
            fb, c, state["stage"], tel = legacy.analyze_pushup(lms, state["stage"])
        elif mode == "PULLUP":
            fb, c, state["stage"], tel = legacy.analyze_pullup(lms, state["stage"])
        elif mode == "TWIST":
            fb, c, tel = legacy.analyze_russian_twist(lms)
        elif mode == "BICEP":
            fb, c, state["stage"], tel = legacy.analyze_bicep_curl(lms, state["stage"])
        elif mode == "HAMMER":
            fb, c, state["stage"], tel = legacy.analyze_hammer_curl(lms, state["stage"])
        elif mode == "LATERAL":
            fb, c, state["stage"], tel = legacy.analyze_lateral_raise(lms, state["stage"])
        elif mode == "PRESS":
            fb, c, state["stage"], tel = legacy.analyze_shoulder_press(
                lms, state["stage"], config_legacy.PRESS_ELBOW_FORWARD_REFERENCE,
                config_legacy.PRESS_ELBOW_BACK_REFERENCE)
        else:
            raise ValueError(mode)
        return fb, c, state["stage"], tel

    return run


def main():
    # Legacy-equivalent build: right side only, no visibility gate, no
    # calibration validation - exactly what the original code did.
    specs = build_specs(side="r", calib_side="r", gates=False, validate=False)
    # Only the ten exercises the original engine implemented can be compared
    # against it; the twelve new ones have no reference to be identical to.
    specs = {k: v for k, v in specs.items() if k in LEGACY_MODES}
    recordings = sorted(glob.glob("golden_dataset/*.csv"))

    total = mismatches = 0
    failures = []

    for mode, spec in specs.items():
        for path in recordings:
            frames = read_frames(path)
            run_legacy = legacy_runner(mode)
            state = spec.initial_state()
            for i, lms in enumerate(frames):
                l_fb, l_c, l_stage, l_tel = run_legacy(lms)
                n_fb, n_c, state, n_tel = analyze(spec, lms, state)
                n_stage = state.get("stage")
                total += 1
                if (l_fb, l_c, l_tel) != (n_fb, n_c, n_tel) or (
                        spec.rep is not None and l_stage != n_stage):
                    mismatches += 1
                    if len(failures) < 12:
                        failures.append(
                            f"{mode:<8} {os.path.basename(path):<26} frame {i}\n"
                            f"    legacy: {l_fb!r} {l_c} stage={l_stage} {l_tel}\n"
                            f"    spec  : {n_fb!r} {n_c} stage={n_stage} {n_tel}")

    print(f"compared {total:,} frames across {len(specs)} exercises x {len(recordings)} recordings")
    if mismatches:
        print(f"\nFAIL - {mismatches:,} mismatching frames ({mismatches / total:.2%})\n")
        print("\n".join(failures))
        return 1
    print("PASS - the declarative engine is frame-for-frame identical to the original")
    return 0


if __name__ == "__main__":
    sys.exit(main())
