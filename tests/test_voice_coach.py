"""Checks the windowed voice coach (voice_coach.py).

Part 1 - unit checks on synthetic frame streams: flicker, one-frame noise,
sustained injury, camera gate, idle silence.
Part 2 - replays every golden recording (looped to a ~realistic set length at
30 fps) and compares how many times the OLD browser logic would have spoken
(every change of feedback text, cancelling the previous sentence) against the
number of cues the coach produces.

Run: python tests/test_voice_coach.py
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.chdir(REPO)

from calibration import read_frames                         # noqa: E402
from exercise_specs import GOLDEN_CSV                       # noqa: E402
from engine import SPECS, REP_TRANSITIONS, HOLD_MODES       # noqa: E402
from spec_framework import GREEN, ORANGE, RED, WHITE, YELLOW, analyze  # noqa: E402
from voice_coach import VoiceCoach, URGENT_STREAK           # noqa: E402

FPS = 30.0
LOOPS = 3


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def feed(coach, clock, frames):
    """frames: list of (feedback, color[, rep_completed]). Returns cues."""
    cues = []
    for f in frames:
        clock.t += 1 / FPS
        cue = coach.observe(f[0], f[1], f[2] if len(f) > 2 else False)
        if cue:
            cues.append((round(clock.t, 2), cue))
    return cues


def unit_checks():
    fails = []

    def check(name, ok, detail=""):
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  -> ' + str(detail) if not ok else ''}")
        if not ok:
            fails.append(name)

    # 1. Rep phase flicker on good reps -> praise, never a correction
    c, k = VoiceCoach(clock=FakeClock()), None
    k = c.clock
    rep = [("GO LOWER", ORANGE)] * 10 + [("PERFECT SQUAT!", GREEN)] * 10 + \
          [("STAND UP", WHITE)] * 8 + [("STAND READY", WHITE, True)] + [("STAND READY", WHITE)] * 11
    cues = feed(c, k, rep * 8)          # 8 reps, 16 s
    kinds = {q["kind"] for _, q in cues}
    check("good reps with phase cues -> praise only", kinds == {"praise"}, cues)
    check("about one cue per 5 s", 2 <= len(cues) <= 4, len(cues))

    # 2. One-frame injury noise is ignored
    c = VoiceCoach(clock=FakeClock())
    noisy = ([("PERFECT PLANK", GREEN)] * 29 + [("STRAIGHTEN HIPS", RED)]) * 6
    cues = feed(c, c.clock, noisy)
    check("single-frame injury noise not spoken",
          all(q["kind"] == "praise" for _, q in cues), cues)

    # 3. Sustained injury fault -> immediate urgent cue, no repeat 1 s later
    c = VoiceCoach(clock=FakeClock())
    cues = feed(c, c.clock, [("PERFECT PLANK", GREEN)] * 20 + [("STRAIGHTEN HIPS", RED)] * 60)
    urgent = [(t, q) for t, q in cues if q["urgent"]]
    check("sustained injury spoken urgently", len(urgent) == 1, cues)
    if urgent:
        check("urgent fires within ~0.3 s of fault start",
              urgent[0][0] <= (20 + URGENT_STREAK) / FPS + 0.01, urgent[0][0])

    # 4. Never reaching depth -> ROM cue
    c = VoiceCoach(clock=FakeClock())
    cues = feed(c, c.clock, ([("GO LOWER", ORANGE)] * 20 + [("STAND UP", WHITE)] * 10) * 12)
    check("never reaching depth -> 'Go lower'",
          cues and cues[0][1]["text"] == "Go lower.", cues)
    check("second identical correction says 'Still'",
          len(cues) > 1 and cues[1][1]["text"].startswith("Still"), cues)

    # 4b. Reps completed -> no ROM cue even if GREEN is rare (leg-extension case)
    c = VoiceCoach(clock=FakeClock())
    cyc = [("EXTEND HIGHER", ORANGE)] * 40 + [("FULL EXTENSION - SQUEEZE", GREEN)] * 2 + \
          [("LOWER SLOWLY", YELLOW)] * 20 + [("EXTEND HIGHER", ORANGE, True)]
    cues = feed(c, c.clock, cyc * 8)
    check("reps completed -> no range-of-motion nag",
          all(q["kind"] == "praise" for _, q in cues), cues)

    # 4c. Urgent cues never stack: a fault that persists is urgent once, then windowed
    c = VoiceCoach(clock=FakeClock())
    cues = feed(c, c.clock, [("TOO DEEP (SPINE RISK)", RED)] * 30 * 14)   # 14 s
    times = [t for t, _ in cues]
    check("persistent fault: one urgent cue, then 'Still' every window",
          sum(q["urgent"] for _, q in cues) == 1
          and all(q["text"].startswith("Still") for _, q in cues[1:]), cues)
    check("no two cues closer than 2.5 s",
          all(b - a >= 2.5 for a, b in zip(times, times[1:])), times)

    # 4d. YOUR CASE: lateral raises that complete but with bent arms -> no praise
    c = VoiceCoach(clock=FakeClock())
    bent = [("LOWER ARMS", YELLOW)] * 8 + [("RAISE ARMS HIGHER", ORANGE)] * 10 + \
           [("STRAIGHTEN ARMS (TOO BENT)", RED)] * 15 + [("LOWER ARMS", YELLOW, True)] + [("LOWER ARMS", YELLOW)] * 6
    cues = feed(c, c.clock, bent * 8)
    check("bent-arm lateral raises -> never praised",
          cues and all(q["kind"] != "praise" for _, q in cues), cues)
    check("bent-arm lateral raises -> told to straighten arms",
          cues and "straighten arms" in cues[0][1]["text"].lower(), cues)

    # 4e. Reps that complete but never reach the target height -> no praise
    c = VoiceCoach(clock=FakeClock())
    short = [("RAISE ARMS HIGHER", ORANGE)] * 20 + [("LOWER ARMS", YELLOW, True)] + [("LOWER ARMS", YELLOW)] * 9
    cues = feed(c, c.clock, short * 8)
    check("partial-range reps -> cue, not praise",
          cues and all(q["kind"] != "praise" for _, q in cues), cues)

    # 4f. Mostly clean with one bad rep -> 'Mostly good reps. Watch: ...'
    c = VoiceCoach(clock=FakeClock())
    good = [("RAISE ARMS HIGHER", ORANGE)] * 12 + [("PERFECT HEIGHT", GREEN)] * 6 + \
           [("LOWER ARMS", YELLOW, True)] + [("LOWER ARMS", YELLOW)] * 5
    badrep = [("RAISE ARMS HIGHER", ORANGE)] * 12 + [("STRAIGHTEN ARMS (TOO BENT)", RED)] * 6 + \
             [("LOWER ARMS", YELLOW, True)] + [("LOWER ARMS", YELLOW)] * 5
    cues = feed(c, c.clock, (good * 4 + badrep) * 2)
    check("mostly clean reps -> 'Mostly good reps. Watch'",
          cues and cues[0][1]["text"].startswith("Mostly good reps"), cues)

    # 4g. One noisy fault frame inside a good rep does not spoil it
    c = VoiceCoach(clock=FakeClock())
    noisy_good = good[:5] + [("STRAIGHTEN ARMS (TOO BENT)", RED)] + good[5:]
    cues = feed(c, c.clock, noisy_good * 8)
    check("single noisy frame -> rep still clean (praise)",
          cues and cues[0][1]["kind"] == "praise", cues)

    # 5. Camera gate
    c = VoiceCoach(clock=FakeClock())
    cues = feed(c, c.clock, [("ADJUST CAMERA - BODY NOT FULLY VISIBLE (r knee / r ankle)", YELLOW)] * 160)
    check("body not visible -> camera cue", cues and cues[0][1]["kind"] == "camera", cues)

    # 6. Idle -> silence
    c = VoiceCoach(clock=FakeClock())
    check("idle standing -> silent", feed(c, c.clock, [("STAND READY", WHITE)] * 300) == [])
    return fails


def golden_replay():
    print(f"\n{'ID':<10}{'SECS':>5}{'OLD':>6}{'NEW':>5}  CUES (time: text)")
    print("-" * 110)
    for mode, spec in SPECS.items():
        frames = read_frames(os.path.join("golden_dataset", GOLDEN_CSV[mode])) * LOOPS
        if not frames:
            continue
        coach, clock = VoiceCoach(clock=FakeClock()), None
        clock = coach.clock
        state = spec.initial_state()
        old_spoken, last_text, cues = 0, "", []
        for lms in frames:
            clock.t += 1 / FPS
            prev = state.get("stage")
            fb, clr, state, _ = analyze(spec, lms, state)
            done = mode in REP_TRANSITIONS and prev == REP_TRANSITIONS[mode][0] \
                and state.get("stage") == REP_TRANSITIONS[mode][1]
            if fb != last_text:                 # the old WorkoutView.jsx behaviour
                old_spoken += 1
                last_text = fb
            cue = coach.observe(fb, clr, done, is_hold=mode in HOLD_MODES)
            if cue:
                cues.append(f"{clock.t:4.1f}s{'!' if cue['urgent'] else ''} {cue['text']}")
        print(f"{mode:<10}{len(frames) / FPS:>5.0f}{old_spoken:>6}{len(cues):>5}  " + " | ".join(cues))


if __name__ == "__main__":
    print("Unit checks")
    failed = unit_checks()
    golden_replay()
    print(f"\n{len(failed)} unit check(s) failed" if failed else "\nAll unit checks passed")
    sys.exit(1 if failed else 0)
