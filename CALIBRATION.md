# Threshold Provenance & Validation

Regenerate with `python tests/test_all_exercises.py`. Every angle threshold in the
form engine is either derived from a golden recording, clamped to an anatomically
plausible window, or replaced by a documented fallback - and this table says which,
for every exercise, along with how the analyzer behaves when replayed against that
same recording.

| Exercise | Status | Threshold source | Reps found | Injury faults on correct form | Notes |
|---|---|---|---|---|---|
| Squats | **live** | `golden` | 3 | 42% | depth 90 deg |
| Planks | **live** | `golden` | n/a (hold) | 13% | derived from recording |
| Tricep Dips | **live** | `golden` | 3 | 0% | derived from recording |
| Pushups | **live** | `golden` | 9 | 5% | derived from recording |
| Pullups | **live** | `golden` | 2 | 0% | derived from recording |
| Russian Twists | **live** | `golden` | n/a (hold) | 0% | derived from recording |
| Bicep Curls | **live** | `golden` | 4 | 0% | derived from recording |
| Hammer Curls | **live** | `golden` | 4 | 1% | derived from recording |
| Lateral Raises | **live** | `golden` | 5 | 15% | capped at 85 deg |
| Shoulder Press | **live** | `golden` | 5 | 0% | derived from recording |
| Bench Press | draft | `clamped` | 3 | 0% | derived 26 deg is outside the plausible 45-110 deg window (likely camera-angle foreshortening); clamped to 45 |
| Incline Bench Press | draft | `clamped` | 3 | 3% | derived 31 deg is outside the plausible 45-110 deg window (likely camera-angle foreshortening); clamped to 45 |
| Decline Bench Press | draft | `clamped` | 3 | 35% | derived 24 deg is outside the plausible 45-110 deg window (likely camera-angle foreshortening); clamped to 45 |
| Chest Fly Machine | draft | `golden` | 0 | 0% | open 95 deg |
| Deadlift | draft | `fallback` | 0 | 0% | joint barely moves in recording (range 24 deg < 60 deg); joint barely moves in recording (range 24 deg < 60 de |
| Romanian Deadlift | **live** | `golden` | 1 | 0% | hinge to 76 deg |
| Hip Thrust | **live** | `golden` | 3 | 0% | lockout 175 deg |
| Lat Pulldown | **live** | `clamped` | 1 | 0% | derived 29 deg is outside the plausible 30-110 deg window (likely camera-angle foreshortening); clamped to 30 |
| T-Bar Row | draft | `fallback` | 0 | 0% | joint barely moves in recording (range 38 deg < 70 deg) |
| Leg Extension | **live** | `golden` | 3 | 0% | extend to 157 deg |
| Leg Raises | **live** | `golden` | 4 | 0% | raise to 47 deg |
| Tricep Pushdown | draft | `golden` | 2 | 0% | extend to 167 deg |

## What the status values mean

- **`golden`** - derived from that exercise's own recording, which passed both
  validation checks: the joint actually moved, and MediaPipe could actually see it.
- **`clamped`** - derived successfully but landed outside an anatomically plausible
  window, so it was pulled back to that window's edge. This is almost always camera
  foreshortening - a side-on view compresses the 2D projection of a joint angle,
  most visibly on the bench-press family.
- **`fallback`** - the recording could not support a threshold at all, so a
  documented population range is used instead. Two recordings fail this way:
  `Deadlift.csv` (hip angle moves only 24 degrees across the whole clip - filmed
  front-on, where a hinge is nearly invisible in 2D) and `T bar row.csv` (elbow
  moves only 38 degrees; the pull is not in the data).

## Two bugs this validation surfaced

1. **The original engine read only the RIGHT side of the body.** MediaPipe emits a
   full 33-point skeleton regardless, interpolating landmarks it cannot see, so an
   occluded limb produced confident but invented angles rather than an error. On
   `Squats.csv` the right leg sits at 0.36 mean visibility - the shipped squat depth
   threshold was derived from a leg the model was mostly guessing at. Reading
   whichever side is actually visible cut pushup false positives from 25% to 5%.
2. **A direction-agnostic lean check.** `segment_lean` measures deviation from
   vertical without a sign, so the Romanian deadlift's lockout check reported frames
   where the athlete was still legitimately hinged FORWARD as leaning BACK (10% of a
   correct recording). It now only applies at a true lockout, and is phrased
   direction-neutrally because that is all a single camera can honestly claim.

## Known limitations, stated rather than hidden

- **Squats** log `TOO DEEP (SPINE RISK)` on 42% of frames of the reference recording.
  This is pre-existing, not a regression - the identical rate was measured against
  the original engine. The reference squat is genuinely very deep, and the threshold
  treats knee flexion past ~70 degrees as a spine risk, which is a debatable clinical
  stance rather than a coding bug. Flagged for a decision.
- **Lateral raises** (15%) and **planks** (13%) are likewise pre-existing.
- **Hip thrust** deliberately does NOT check lockout hyperextension: the
  shoulder-hip-knee angle saturates at 180 degrees, so a neutral lockout and an
  over-arched one are the same number to a single camera.
- **Leg raises** cues the brace rather than logging a lumbar injury, for the same
  reason - whether the lower back actually arches depends on bracing the camera
  cannot see.
- Seven exercises (bench press family, chest fly, deadlift, T-bar row, tricep
  pushdown) are drafted in `exercise_specs.py` but **disabled** until they have been
  tuned and measured the same way. A spec that has not been validated has no
  business giving a user injury advice.
