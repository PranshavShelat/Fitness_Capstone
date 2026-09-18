"""Replays every exercise against its own golden recording and reports what the
analyzer actually does with it.

This is the honest counterpart to the parity test. Parity proves the rewrite
did not change behaviour; this measures whether the behaviour is any GOOD - on
a recording of the movement performed correctly, the app should count reps and
should NOT be shouting injury warnings. A high red-fault rate here is a false
positive rate, because the reference recording is the closest thing this project
has to labelled correct form.
"""
import collections
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.chdir(REPO)

from calibration import read_frames                                  # noqa: E402
from exercise_specs import GOLDEN_CSV, build_specs                   # noqa: E402
from injury_knowledge import MISHAP_EXPLANATIONS                      # noqa: E402
from spec_framework import GREEN, RED, analyze                       # noqa: E402

# A false positive is measured against what the app actually LOGS, not against
# what it colours red: server.py only writes a message into the mishap log if it
# appears in MISHAP_EXPLANATIONS, so red-coloured pure coaching ("PULL HIGHER")
# never reaches a report and is not a false injury warning.
# A logged injury fault on a correct-form recording is a false positive. Above this
# share of frames the check is doing more harm than good and should be retuned
# or switched off rather than shipped - the same standard that got the
# shoulder-press elbow-z checks disabled.
FALSE_POSITIVE_LIMIT = 0.10


def main():
    specs = build_specs()
    if "--all" not in sys.argv:
        specs = {k: v for k, v in specs.items() if v.enabled}
    rows, problems = [], []

    for spec_id, spec in specs.items():
        frames = read_frames(os.path.join("golden_dataset", GOLDEN_CSV[spec_id]))
        state = spec.initial_state()
        reps = gated = red = green = 0
        prev_stage = state.get("stage")
        counts = collections.Counter()

        for lms in frames:
            fb, color, state, _tel = analyze(spec, lms, state)
            counts[fb] += 1
            if fb in MISHAP_EXPLANATIONS:
                red += 1
            elif color == GREEN:
                green += 1
            if fb.startswith(spec.gate_message.split(" - ")[0]) and "VISIB" in fb.upper() or \
                    "CAMERA" in fb.upper() or "NOT VISIBLE" in fb.upper():
                gated += 1
            if spec.rep:
                stage = state.get("stage")
                if prev_stage == spec.rep.work_stage and stage == spec.rep.rest_stage:
                    reps += 1
                prev_stage = stage

        n = max(len(frames), 1)
        rows.append((spec_id, spec.name, len(frames), reps, green / n, red / n, gated / n,
                     counts.most_common(1)[0][0] if counts else "-",
                     spec.calibration_source))

        if spec.rep and reps == 0 and gated / n < 0.5:
            problems.append(f"{spec_id}: counted 0 reps on its own reference recording")
        if red / n > FALSE_POSITIVE_LIMIT:
            problems.append(
                f"{spec_id}: {red / n:.0%} of frames flag an injury fault on correct form "
                f"(limit {FALSE_POSITIVE_LIMIT:.0%}) - most common: {counts.most_common(1)[0][0]!r}")

    print(f"{'ID':<10}{'EXERCISE':<21}{'FRM':>5}{'REPS':>5}{'GOOD':>7}{'FAULT':>7}{'GATED':>7}  "
          f"{'CALIB':<9}TOP MESSAGE")
    print("-" * 118)
    for r in rows:
        print(f"{r[0]:<10}{r[1]:<21}{r[2]:>5}{r[3]:>5}{r[4]:>7.0%}{r[5]:>7.0%}{r[6]:>7.0%}  "
              f"{r[8]:<9}{r[7][:34]}")

    print()
    if problems:
        print(f"{len(problems)} issue(s) to address:")
        for p in problems:
            print("  - " + p)
        return 1
    print("All 22 exercises count reps and stay under the false-positive limit on correct form.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
