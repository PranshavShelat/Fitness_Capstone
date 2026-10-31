"""Stress test: does the engine stay honest when the camera view is BAD?

test_all_exercises.py replays clean studio-style recordings. Real use is a
laptop webcam: legs cut off at the bottom of the frame, jittery tracking, the
odd one-frame glitch. MediaPipe never says "I can't see that" - it keeps
emitting all 33 landmarks and simply guesses the hidden ones - so a fragile
engine turns those guesses into phantom reps and impossible angles (a real
session logged 25 squats in two minutes and an 11 deg knee angle).

Each golden recording is replayed under five deterministic corruptions:

  clean         unchanged (the robust engine must not lose real reps)
  jitter        small random shake on every landmark (normal webcam noise)
  glitch        5% of frames: the whole skeleton jumps somewhere random
  legs_hidden   knees/ankles/feet below the frame: low visibility, guessed
                positions - what a laptop on a desk actually sees
  side_flicker  left/right visibility wobbles, so the "better side" flips

and the numbers are compared with the robust checks OFF (the old behaviour)
and ON. Run:  python tests/test_robustness.py
"""
import os
import random
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.chdir(REPO)

from calibration import CsvLandmark, read_frames                     # noqa: E402
from exercise_specs import GOLDEN_CSV, build_specs                   # noqa: E402
from injury_knowledge import MISHAP_EXPLANATIONS                      # noqa: E402
from spec_framework import analyze                                    # noqa: E402

LEG_IDX = range(25, 33)          # knees, ankles, heels, feet
LEFT = [11, 13, 15, 23, 25, 27, 29, 31]
RIGHT = [12, 14, 16, 24, 26, 28, 30, 32]


def corrupt(frames, kind, seed=7):
    rnd = random.Random(seed)
    out = []
    for f in frames:
        lm = [CsvLandmark(p.x, p.y, p.z, p.visibility) for p in f]
        if kind == "jitter":
            for p in lm:
                p.x += rnd.gauss(0, 0.012); p.y += rnd.gauss(0, 0.012)
        elif kind == "glitch" and rnd.random() < 0.05:
            dx, dy = rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3)
            for p in lm:
                p.x += dx + rnd.gauss(0, 0.08); p.y += dy + rnd.gauss(0, 0.08)
        elif kind == "legs_hidden":
            for i in LEG_IDX:
                p = lm[i]
                p.visibility = rnd.uniform(0.02, 0.15)
                p.y = 1.0 + rnd.uniform(0.0, 0.25) if i >= 27 else p.y + rnd.gauss(0, 0.07)
                p.x += rnd.gauss(0, 0.07)
        elif kind == "side_flicker":
            a, b = rnd.uniform(0.6, 1.0), rnd.uniform(0.6, 1.0)
            for i in LEFT:
                lm[i].visibility *= a
            for i in RIGHT:
                lm[i].visibility *= b
        out.append(lm)
    return out


def replay(spec, frames):
    state = spec.initial_state()
    prev = state.get("stage")
    reps = faults = gated = 0
    for lm in frames:
        fb, _c, state, _t = analyze(spec, lm, state)
        if fb in MISHAP_EXPLANATIONS:
            faults += 1
        if "VISIBLE" in fb or "CAN'T SEE" in fb:
            gated += 1
        if spec.rep:
            stage = state.get("stage")
            if prev == spec.rep.work_stage and stage == spec.rep.rest_stage:
                reps += 1
            prev = stage
    n = max(len(frames), 1)
    return reps, faults / n, gated / n


# Reps actually performed in each golden recording, counted by hand from the
# rep-angle trace (a full rest -> worked -> rest cycle; a half rep at the start
# or end of a clip does not count). Several differ from what the ORIGINAL engine
# reported: it counted a rep before any lift on curls/raises/pull-ups (its
# counter started in the worked stage), counted a one-frame tracking glitch in
# the squat clip, and counted the first lowering of a hip thrust filmed from the top.
TRUE_REPS = {"SQUAT": 2, "DIP": 3, "PUSHUP": 9, "PULLUP": 1, "BICEP": 3, "HAMMER": 3,
             "LATERAL": 4, "PRESS": 5, "RDL": 1, "HIPTHRUST": 2, "PULLDOWN": 1,
             "LEGEXT": 2, "LEGRAISE": 4}

# The ORIGINAL engine's starting stages, so the "old" column really is the old app
# (the robust build starts every counter at rest; see spec_framework check 4).
ORIGINAL_INITIAL = {"HIPTHRUST": "DOWN", "LEGEXT": "DOWN", "LEGRAISE": "DOWN"}  # others "UP"


def set_mode(spec, sid, robust):
    spec.robust = robust
    if spec.rep:
        spec.rep.initial = spec.rep.rest_stage if robust else ORIGINAL_INITIAL.get(sid, "UP")
    spec.starts_in_work = robust and sid == "PRESS"


KINDS = ["clean", "jitter", "glitch", "legs_hidden", "side_flicker"]


def main():
    specs = {k: v for k, v in build_specs().items() if v.enabled}
    totals = {k: {"old_extra": 0, "new_extra": 0, "old_fault": 0.0, "new_fault": 0.0} for k in KINDS}
    lost_real_reps = []
    print(f"{'EXERCISE':<11}{'CORRUPTION':<14}{'TRUE':>5}{'OLD REPS':>9}{'NEW REPS':>9}"
          f"{'OLD FAULT':>10}{'NEW FAULT':>10}{'NEW GATED':>10}")
    for sid, spec in specs.items():
        frames = read_frames(os.path.join("golden_dataset", GOLDEN_CSV[sid]))
        true_reps = TRUE_REPS.get(sid, 0)
        for kind in KINDS:
            data = frames if kind == "clean" else corrupt(frames, kind)
            set_mode(spec, sid, False)
            o_reps, o_fault, _ = replay(spec, data)
            set_mode(spec, sid, True)
            n_reps, n_fault, n_gated = replay(spec, data)
            t = totals[kind]
            t["old_extra"] += max(0, o_reps - true_reps); t["new_extra"] += max(0, n_reps - true_reps)
            t["old_fault"] += o_fault; t["new_fault"] += n_fault
            if kind == "clean" and n_reps != true_reps:
                lost_real_reps.append((sid, true_reps, n_reps, n_gated))
            if spec.rep or o_fault or n_fault:
                print(f"{sid:<11}{kind:<14}{true_reps if spec.rep else '-':>5}"
                      f"{o_reps if spec.rep else '-':>9}{n_reps if spec.rep else '-':>9}"
                      f"{o_fault:>10.0%}{n_fault:>10.0%}{n_gated:>10.0%}")
        set_mode(spec, sid, True)

    n = len(specs)
    print("\nSummary across all live exercises (phantom reps = counted beyond the true count):")
    print(f"{'CORRUPTION':<14}{'PHANTOM OLD':>12}{'PHANTOM NEW':>12}{'AVG FAULT OLD':>15}{'AVG FAULT NEW':>15}")
    for kind in KINDS:
        t = totals[kind]
        print(f"{kind:<14}{t['old_extra']:>12}{t['new_extra']:>12}{t['old_fault'] / n:>15.1%}{t['new_fault'] / n:>15.1%}")
    if lost_real_reps:
        print("\nFAIL - clean recordings miscounted (true -> counted): "
              + ", ".join(f"{sid} {t}->{n}" for sid, t, n, _g in lost_real_reps))
        return 1
    print(f"\nPASS - all {len(TRUE_REPS)} rep exercises count exactly the true reps on clean recordings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
