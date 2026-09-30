"""Windowed voice coaching: judge a stretch of the set, then say ONE thing.

Why this exists: the form engine produces a message every frame (~20-30 per
second), and many of those messages are just the phase of the rep - "GO LOWER"
on the way down, "LOWER SLOWLY" on the way back - which flip several times on
every perfectly good rep. Speaking each change made the voice erratic: it cut
itself off mid-sentence and read out transitional cues as if they were faults.

VoiceCoach instead collects the per-frame results for a WINDOW (5 s by default)
and, when the window closes, decides what the whole window says about the set:

  1. injury fault  - a MISHAP_EXPLANATIONS message present in a meaningful share
                     of the window (a few noisy frames are not enough)
  2. camera        - the body was not visible for most of the window
  3. coaching cue  - a range-of-motion / tempo cue that dominated the window AND
                     the athlete never reached the target position (no rep
                     completed, almost no GREEN frames) - otherwise "GO LOWER"
                     was only the transition into a good rep
  4. per-rep       - every completed rep is judged on its own: CLEAN only if it
                     reached the target position with no fault held during it.
                     Bad reps -> the fault that spoiled them; mostly clean ->
                     "Mostly good reps. Watch: ..."; all clean -> praise that
                     counts ONLY the clean reps. Finishing the movement is not
                     enough to be called a good rep.
  5. silence       - the athlete was idle / resting

One exception to the window: an injury fault held for URGENT_STREAK consecutive
frames is spoken immediately, because waiting up to 5 s to say "spine risk" is
the wrong trade-off. After an urgent cue the window restarts, and the same fault
cannot be urgent again for URGENT_COOLDOWN_SECONDS - the windows take it from
there - so the voice never stacks cues on top of each other.

Pure logic, no audio - server.py sends the cue to the browser, main.py speaks it
with gTTS. That also means it is unit-testable (tests/test_voice_coach.py).
"""
import time
from collections import Counter

from injury_knowledge import MISHAP_EXPLANATIONS
from spec_framework import GREEN, ORANGE, RED, WHITE, YELLOW

WINDOW_SECONDS = 5.0
# A window with fewer frames than this (tab in background, connection hiccup)
# is too thin to judge - say nothing rather than guess.
MIN_FRAMES = 10
# Share of the window's frames an injury fault must appear in to be spoken.
INJURY_SHARE = 0.25
# Share of frames the camera gate must fire in to ask the user to reposition.
GATE_SHARE = 0.50
# A coaching cue is only spoken if cues filled this much of the window...
CUE_SHARE = 0.40
# ...the specific cue itself filled at least this much...
CUE_MIN_SHARE = 0.15
# ...and the athlete reached a GREEN (target) position in less than this share.
CUE_MAX_GOOD_SHARE = 0.10
# Praise needs this share of GREEN frames, or at least one completed rep.
GOOD_SHARE = 0.30
# Consecutive frames of the same injury fault that trigger an immediate cue.
URGENT_STREAK = 8
# After an urgent cue, the same fault is left to the normal 5 s windows (which
# say "Still: ...") for this long, so urgent cues cannot stack on top of them.
URGENT_COOLDOWN_SECONDS = 15.0
# An urgent cue never lands within this long of the previous cue of any kind -
# two sentences back to back just talk over each other.
MIN_GAP_SECONDS = 2.5

# Posture faults that are NOT injury risks (so not in MISHAP_EXPLANATIONS) but
# still make a rep "not clean". Unlike range cues such as "RAISE ARMS HIGHER" or
# "GO LOWER" - which appear on every good rep on the way to the target - these
# only appear when the athlete is actually doing something wrong.
TECHNIQUE_FAULTS = {
    "STRAIGHTEN ARMS (TOO BENT)", "STRAIGHTEN KNEES", "SITTING TOO FAR BACK",
    "KNEES BENDING - HINGE, DON'T SQUAT", "MOVE YOUR FEET (SHINS SHOULD BE VERTICAL)",
    "HIPS LIFTING OFF THE SEAT", "KEEP LOWER BACK PRESSED DOWN", "STRAIGHTEN YOUR LEGS",
    "PIN ELBOWS TO YOUR SIDES", "HINGE FORWARD MORE", "FIX FORWARD LEAN",
}
# A technique fault filling this share of a window is spoken even mid-set.
TECH_SHARE = 0.25
# A fault spoils a rep only if it is HELD: at least this many frames AND this
# share of the rep. Measured on the golden (correct-form) recordings: pose noise
# is 1-3 frames per rep, and a brief overshoot at the top of a lateral raise is
# under ~20% of the rep - neither should turn a good rep into a "bad" one.
REP_FAULT_MIN_FRAMES = 4
REP_FAULT_MIN_SHARE = 0.15
# Frames at the target (GREEN) position needed for a rep to count as full range.
REP_GOOD_MIN_FRAMES = 1
# A "rep" shorter than this (~0.25 s) is a stage-machine artifact - e.g. the
# first frames after starting mid-movement - not a real rep, so it is not judged.
MIN_REP_FRAMES = 8

# Higher = more important when two cues compete in one window.
_SEVERITY = {RED: 3, ORANGE: 2, YELLOW: 1}

_PRAISE_REPS = ["Good reps, keep it going.", "Nice and clean, keep that form.",
                "Solid reps.", "That's it, same again."]
_PRAISE_HOLD = ["Good position, hold it.", "Solid hold, keep breathing.",
                "Looking steady, stay tight.", "Great form, keep holding."]


def _is_gate(message):
    up = message.upper()
    return "NOT VISIBLE" in up or "NOT FULLY VISIBLE" in up


def to_spoken(message):
    """'TOO DEEP (SPINE RISK)' -> 'Too deep, spine risk.' Shouty HUD text reads
    badly through a speech engine, and brackets are read literally by some."""
    text = message.replace("(", ", ").replace(")", "").replace(" - ", ", ")
    text = text.replace("!", "").replace(" ,", ",").strip(" ,")
    text = text.lower()
    text = text[:1].upper() + text[1:]
    return text if text.endswith((".", "?")) else text + "."


class VoiceCoach:
    def __init__(self, window_seconds=WINDOW_SECONDS, clock=time.monotonic):
        self.window_seconds = window_seconds
        self.clock = clock
        self._last_cue_key = None
        self._praise_i = 0
        self._last_urgent = {}          # message -> time it was last spoken urgently
        self._last_cue_at = -1e9
        self._rep_results = []
        self.reset()

    def reset(self):
        """Call on exercise switch - a window must never mix two exercises."""
        self._rep_msgs = Counter()      # frames per message within the current rep
        self._rep_good = 0
        self._window_start = None
        self._counts = Counter()
        self._colors = {}
        self._frames = 0
        self._reps = 0
        self._streak_msg = None
        self._streak = 0

    # ------------------------------------------------------------------
    def observe(self, feedback, color, rep_completed=False, is_hold=False):
        """Feed one analysed frame. Returns a cue dict when something should be
        spoken, else None. Cue: {"text", "kind", "urgent", "source"}."""
        now = self.clock()
        if self._window_start is None:
            self._window_start = now

        self._frames += 1
        self._counts[feedback] += 1
        self._colors[feedback] = tuple(color)
        self._rep_msgs[feedback] += 1
        if tuple(color) == GREEN:
            self._rep_good += 1
        if rep_completed:
            self._reps += 1
            self._rep_results.append(self._judge_rep())
            self._rep_msgs = Counter()
            self._rep_good = 0

        # --- urgent path: sustained injury fault ------------------------
        if feedback in MISHAP_EXPLANATIONS:
            self._streak = self._streak + 1 if feedback == self._streak_msg else 1
            self._streak_msg = feedback
            if (self._streak == URGENT_STREAK
                    and now - self._last_urgent.get(feedback, -1e9) >= URGENT_COOLDOWN_SECONDS
                    and now - self._last_cue_at >= MIN_GAP_SECONDS):
                self._last_urgent[feedback] = now
                self._last_cue_at = now
                self._last_cue_key = feedback
                self._restart_window(now)
                return {"text": to_spoken(feedback), "kind": "injury",
                        "urgent": True, "source": feedback}
        else:
            self._streak_msg, self._streak = None, 0

        # --- window path ------------------------------------------------
        if now - self._window_start < self.window_seconds:
            return None
        cue = self._summarise(is_hold)
        self._restart_window(now)
        if cue:
            self._last_cue_at = now
        return cue

    def _judge_rep(self):
        """Classify the rep that just finished: ("clean", None), ("fault", msg) or
        ("partial", cue). A rep is clean only if it reached the target position
        and no fault was held during it - completing the movement is not enough."""
        n = max(sum(self._rep_msgs.values()), 1)
        if n < MIN_REP_FRAMES:
            return ("ignored", None)
        faults = {m: c for m, c in self._rep_msgs.items()
                  if (m in MISHAP_EXPLANATIONS or m in TECHNIQUE_FAULTS)
                  and c >= REP_FAULT_MIN_FRAMES and c / n >= REP_FAULT_MIN_SHARE}
        if faults:
            top = max(faults, key=lambda m: (m in MISHAP_EXPLANATIONS, faults[m]))
            return ("fault", top)
        if self._rep_good >= REP_GOOD_MIN_FRAMES:
            return ("clean", None)
        cues = [m for m in self._rep_msgs
                if self._colors.get(m) in _SEVERITY and not _is_gate(m)
                and m not in MISHAP_EXPLANATIONS and m not in TECHNIQUE_FAULTS]
        cue = max(cues, key=lambda m: self._rep_msgs[m]) if cues else None
        return ("partial", cue)

    def _restart_window(self, now):
        self._rep_results = []
        self._window_start = now
        self._counts = Counter()
        self._colors = {}
        self._frames = 0
        self._reps = 0

    # ------------------------------------------------------------------
    def _summarise(self, is_hold):
        n = self._frames
        if n < MIN_FRAMES:
            return None
        share = {m: c / n for m, c in self._counts.items()}

        injuries = [m for m in share if m in MISHAP_EXPLANATIONS and share[m] >= INJURY_SHARE]
        gate = sum(s for m, s in share.items() if _is_gate(m))
        good = sum(s for m, s in share.items() if self._colors[m] == GREEN)
        cues = {m: s for m, s in share.items()
                if m not in MISHAP_EXPLANATIONS and not _is_gate(m)
                and self._colors[m] in _SEVERITY}

        if injuries:
            top = max(injuries, key=lambda m: share[m])
            return self._say(top, to_spoken(top), "injury")

        if gate >= GATE_SHARE:
            gate_msg = max((m for m in share if _is_gate(m)), key=lambda m: share[m])
            return self._say("__gate__", to_spoken(gate_msg.split(" (")[0]), "camera")

        tech = [m for m in share if m in TECHNIQUE_FAULTS and share[m] >= TECH_SHARE]
        if tech:
            top = max(tech, key=lambda m: share[m])
            return self._say(top, to_spoken(top), "form")

        # --- rep-by-rep verdict: only CLEAN reps earn praise --------------
        results = [r for r in self._rep_results if r[0] != "ignored"]
        clean = sum(1 for kind, _ in results if kind == "clean")
        bad = [(kind, what) for kind, what in results if kind != "clean"]
        if bad:
            named = [what for _, what in bad if what]
            top = Counter(named).most_common(1)[0][0] if named else None
            if top:
                if clean > len(bad):
                    self._last_cue_key = top
                    text = "Mostly good reps. Watch: " + to_spoken(top)[0].lower() + to_spoken(top)[1:]
                    return {"text": text, "kind": "form", "urgent": False, "source": top}
                kind = "injury" if top in MISHAP_EXPLANATIONS else "form"
                return self._say(top, to_spoken(top), kind)
        if clean and not is_hold:
            pool = _PRAISE_REPS
            text = pool[self._praise_i % len(pool)]
            self._praise_i += 1
            if clean > 1:
                text = f"{clean} good reps. " + text
            self._last_cue_key = "__praise__"
            return {"text": text, "kind": "praise", "urgent": False, "source": None}

        # A completed rep means the athlete DID reach the worked position, so a
        # range-of-motion cue in that window was only the transition - skip it.
        if sum(cues.values()) >= CUE_SHARE and good < CUE_MAX_GOOD_SHARE and self._reps == 0:
            eligible = [m for m, s in cues.items() if s >= CUE_MIN_SHARE]
            if eligible:
                top = max(eligible, key=lambda m: (_SEVERITY[self._colors[m]], cues[m]))
                return self._say(top, to_spoken(top), "form")

        # Holds (plank, V-hold) have no reps: praise a steady good position.
        if is_hold and good >= GOOD_SHARE:
            pool = _PRAISE_HOLD
            text = pool[self._praise_i % len(pool)]
            self._praise_i += 1
            self._last_cue_key = "__praise__"
            return {"text": text, "kind": "praise", "urgent": False, "source": None}

        # Idle / resting / only neutral stage messages: stay quiet.
        return None

    def _say(self, key, text, kind):
        # Same correction two windows running: say so, instead of repeating the
        # identical sentence, so it sounds like a coach rather than a loop.
        if key == self._last_cue_key and kind != "camera":
            text = "Still: " + text[0].lower() + text[1:]
        self._last_cue_key = key
        return {"text": text, "kind": kind, "urgent": False,
                "source": None if key == "__gate__" else key}
