"""Correct ("perfect") form for every exercise the planner can prescribe.

ONE source of truth, read by three consumers:
  * the workout planner UI   (GET /form-guide -> Dashboard "How to do it")
  * the injury report PDF    ("How each exercise should look" + per-fault numbers)
  * anything else later      (coach chat, voice cues)

What lives here, and where its authority comes from:
  * setup / execution / breathing / mistakes - written coaching cues. Where a
    page in an official manual backs them, it is listed in "sources" (keys from
    injury_knowledge.SOURCES). Where none is listed, the cues are standard
    technique coaching and the UI/PDF says so - nothing pretends to be cited.
  * checkpoints - the NUMBERS. These are NOT typed in here: they are read live
    from the engine's calibrated thresholds (exercise_specs.py, derived from the
    golden_dataset recordings), so the guide a user reads and the camera check
    that grades them can never disagree.
  * FAULT_MEASURES - for each loggable fault, which engine metric shows it and
    what the safe limit is, so the report can say "you reached 63 deg, the
    limit is 70 deg" instead of just "form incorrect".
  * reference_false_alarm_rates() - how often each fault fires on the CORRECT
    reference recording. A fault that fires on good form is reported as
    "low confidence" instead of being presented as fact.

Plain ASCII only (the PDF uses fpdf2's core latin-1 font).
"""
import os
from functools import lru_cache

from injury_knowledge import MISHAP_EXPLANATIONS, SOURCES

# ---------------------------------------------------------------------------
# Written guide. Keys are the display names used by plan.PLANNABLE_EXERCISES.
# "mode" is the engine id (None-free: disabled drafts keep their id so the
# guide lights up automatically once they are enabled).
# ---------------------------------------------------------------------------
GUIDE = {
    "Squats": {
        "mode": "SQUAT",
        "muscles": "Thighs (quads), glutes, hamstrings; core keeps the back steady",
        "setup": [
            "Feet about shoulder-width apart, toes turned out slightly.",
            "Chest up, eyes looking straight ahead, stomach braced.",
        ],
        "execution": [
            "Push your hips back and bend your knees at the same time, as if sitting into a chair.",
            "Keep your knees pointing the same way as your toes the whole time.",
            "Go down until your thighs are about level with the floor, back still flat.",
            "Drive up through your whole foot; hips and shoulders rise at the same speed.",
        ],
        "breathing": "Breathe in and brace before you go down; breathe out as you stand up.",
        "mistakes": [
            "Knees caving inward",
            "Going so deep the hips tuck under and the lower back rounds",
            "Chest dropping so the hips rise first",
        ],
        "sources": [("FM722", "p. 8-8, squat check points"),
                    ("FM722", "p. 9-56, squat to thighs level with the floor")],
    },
    "Planks": {
        "mode": "PLANK",
        "muscles": "Core (abs, obliques), glutes, shoulders",
        "setup": [
            "Forearms on the floor, elbows directly under your shoulders.",
            "Legs straight behind you, feet together or hip-width apart.",
        ],
        "execution": [
            "Lift your hips so your body is one straight line from head to heels.",
            "Squeeze your glutes and pull your belly button toward your spine.",
            "Keep your neck in line - look at the floor just ahead of your hands.",
            "Stop and rest when your hips start to sag, then continue.",
        ],
        "breathing": "Breathe slowly and steadily; do not hold your breath.",
        "mistakes": ["Hips sagging toward the floor", "Hips piked up high", "Knees bent"],
        "sources": [("FM722", "p. 6-11 to 6-14, 4 for the core")],
    },
    "Tricep Dips": {
        "mode": "DIP",
        "muscles": "Triceps, chest, front of shoulders",
        "setup": [
            "Hands on the bars (or bench edge) beside your hips, arms straight.",
            "Shoulders pulled down and back, away from your ears.",
        ],
        "execution": [
            "Bend your elbows and lower yourself straight down, elbows pointing back.",
            "Stop when your upper arms are about level with the floor.",
            "Push back up until your arms are straight, without shrugging.",
        ],
        "breathing": "Breathe in on the way down, out as you push up.",
        "mistakes": ["Going too low (shoulder stretched under body weight)",
                     "Shoulders rolling forward / shrugging", "Elbows flaring out wide"],
        "sources": [("FM722", "p. 6-94, upper arms level with the floor")],
    },
    "Pushups": {
        "mode": "PUSHUP",
        "muscles": "Chest, triceps, front of shoulders; core holds the body line",
        "setup": [
            "Hands directly under your shoulders, slightly wider than shoulder-width.",
            "Body straight from head to heels, stomach and glutes tight.",
        ],
        "execution": [
            "Lower your chest toward the floor with elbows angled back, close to your body.",
            "Go down until your upper arms are about level with the floor.",
            "Push the floor away until your arms are straight; body stays rigid the whole time.",
        ],
        "breathing": "Breathe in going down, out as you push up.",
        "mistakes": ["Hips sagging", "Elbows flaring straight out to the sides",
                     "Half reps that stop well above the floor"],
        "sources": [("FM722", "p. 6-94, push-up check points")],
    },
    "Pullups": {
        "mode": "PULLUP",
        "muscles": "Lats (back), biceps, rear shoulders, grip",
        "setup": [
            "Grip the bar a little wider than shoulder-width, palms facing away.",
            "Start from a full hang, arms straight, shoulders pulled slightly down.",
        ],
        "execution": [
            "Pull your elbows down toward your ribs to lift your chest to the bar.",
            "Get your chin over the bar without kicking or swinging.",
            "Lower yourself slowly all the way back to a straight-arm hang.",
        ],
        "breathing": "Breathe out as you pull up, in as you lower.",
        "mistakes": ["Swinging or kicking to get up", "Stopping short of the bar",
                     "Dropping down fast instead of lowering"],
        "sources": [],
    },
    "Russian Twists": {
        "mode": "TWIST",
        "muscles": "Obliques, abs, hip flexors",
        "setup": [
            "Sit with knees bent, heels on the floor (or lifted for a harder version).",
            "Lean back until your upper body makes a V with your thighs, back straight.",
        ],
        "execution": [
            "Rotate your shoulders - not just your arms - to one side, then the other.",
            "Keep your chest up and the same lean back throughout.",
            "Move under control; speed is not the goal.",
        ],
        "breathing": "Breathe out as you turn to each side.",
        "mistakes": ["Rounding the lower back", "Only moving the arms, not the torso",
                     "Leaning back too far or sitting up too tall"],
        "sources": [],
    },
    "Bicep Curls": {
        "mode": "BICEP",
        "muscles": "Biceps, forearms",
        "setup": [
            "Stand tall, feet hip-width apart, weights at your sides, palms facing forward.",
            "Elbows tucked in against your sides.",
        ],
        "execution": [
            "Curl the weight up by bending only at the elbow - upper arms stay still.",
            "Squeeze at the top without letting the elbows drift forward.",
            "Lower slowly until your arms are fully straight again.",
        ],
        "breathing": "Breathe out as you curl up, in as you lower.",
        "mistakes": ["Elbows moving forward (shoulder doing the work)",
                     "Swinging the body to lift the weight", "Not straightening the arm at the bottom"],
        "sources": [("FM722", "p. 6-62, biceps curl")],
    },
    "Hammer Curls": {
        "mode": "HAMMER",
        "muscles": "Biceps, brachialis, forearms",
        "setup": [
            "Stand tall with dumbbells at your sides, palms facing your body (thumbs up).",
            "Elbows tucked in against your sides.",
        ],
        "execution": [
            "Curl the weights up keeping the thumbs-up grip; only the forearm moves.",
            "Stop when the forearm is near vertical, elbows still at your sides.",
            "Lower slowly to a straight arm.",
        ],
        "breathing": "Breathe out as you curl up, in as you lower.",
        "mistakes": ["Elbows drifting forward", "Swinging the weight", "Rushing the lowering"],
        "sources": [],
    },
    "Lateral Raises": {
        "mode": "LATERAL",
        "muscles": "Side of the shoulders (lateral deltoids)",
        "setup": [
            "Stand tall, light dumbbells at your sides, slight bend in the elbows.",
            "Shoulders relaxed and down - not shrugged.",
        ],
        "execution": [
            "Raise your arms out to the sides, leading with your elbows.",
            "Stop at shoulder height, when your arms are level with the floor.",
            "Lower slowly back to your sides.",
        ],
        "breathing": "Breathe out as you raise, in as you lower.",
        "mistakes": ["Raising above shoulder height (shoulder pinching)",
                     "Arms bent too much (turns into a shrug/row)", "Swinging the weights up"],
        "sources": [("FM722", "p. 6-54, lateral raise")],
    },
    "Shoulder Press": {
        "mode": "PRESS",
        "muscles": "Shoulders, triceps, upper chest",
        "setup": [
            "Weights at shoulder height, elbows bent about 90 deg, wrists directly above elbows.",
            "Stand or sit tall, stomach braced, ribs down.",
        ],
        "execution": [
            "Press the weights straight up over your shoulders until the arms are straight.",
            "Both arms move at the same speed and finish together.",
            "Lower under control back to shoulder height.",
        ],
        "breathing": "Breathe out as you press, in as you lower.",
        "mistakes": ["Leaning back to finish the press", "Wrists dropping behind the elbows",
                     "One arm lagging behind the other", "Elbows flaring wide too early"],
        "sources": [("FM722", "p. 6-47, shoulder press")],
    },
    "Bench Press": {
        "mode": "BENCH",
        "muscles": "Chest, triceps, front of shoulders",
        "setup": [
            "Lie on the bench with eyes under the bar, feet flat on the floor.",
            "Grip slightly wider than shoulder-width; squeeze your shoulder blades together.",
        ],
        "execution": [
            "Lower the bar to your mid-chest with elbows about 45-70 deg from your body.",
            "Touch lightly - no bouncing off the chest.",
            "Press back up until your arms are straight over your shoulders.",
        ],
        "breathing": "Breathe in and brace as you lower, out as you press.",
        "mistakes": ["Elbows flared straight out at 90 deg", "Bouncing the bar off the chest",
                     "Hips lifting off the bench"],
        "sources": [],
    },
    "Inclined Bench Press": {
        "mode": "INCLINE",
        "muscles": "Upper chest, front of shoulders, triceps",
        "setup": [
            "Bench set to a moderate incline (about 30-45 deg).",
            "Feet flat, shoulder blades squeezed together and down.",
        ],
        "execution": [
            "Lower the bar or dumbbells to the upper chest, elbows angled below shoulder level.",
            "Press up and slightly back so the weight finishes over your shoulders.",
        ],
        "breathing": "Breathe in as you lower, out as you press.",
        "mistakes": ["Incline set too steep (turns into a shoulder press)",
                     "Elbows flared out wide", "Arching off the bench"],
        "sources": [],
    },
    "Decline Bench Press": {
        "mode": "DECLINE",
        "muscles": "Lower chest, triceps",
        "setup": [
            "Hook your legs securely under the pads before taking the weight.",
            "Shoulder blades squeezed together, grip slightly wider than shoulders.",
        ],
        "execution": [
            "Lower the bar under control to the lower chest.",
            "Press straight back up over your chest until the arms are straight.",
        ],
        "breathing": "Breathe in as you lower, out as you press.",
        "mistakes": ["Letting the bar drift toward the face or neck", "Bouncing off the chest",
                     "Flaring the elbows wide"],
        "sources": [],
    },
    "Chest Fly Machine": {
        "mode": "FLY",
        "muscles": "Chest, front of shoulders",
        "setup": [
            "Seat height set so the handles are at chest level.",
            "Back flat against the pad, slight bend in the elbows.",
        ],
        "execution": [
            "Bring the handles together in a wide arc, as if hugging a tree.",
            "Squeeze the chest for a moment when the hands meet.",
            "Open slowly until you feel a stretch - not past your shoulders.",
        ],
        "breathing": "Breathe out as you bring the handles together, in as you open.",
        "mistakes": ["Opening too far behind the body", "Bending the elbows into a press",
                     "Letting the weight stack slam"],
        "sources": [],
    },
    "Deadlift": {
        "mode": "DEADLIFT",
        "muscles": "Glutes, hamstrings, lower and upper back, grip",
        "setup": [
            "Bar over the middle of your feet, feet hip-width apart.",
            "Hinge down and grip just outside your legs; shins touch the bar.",
            "Flat back, chest up, shoulders slightly in front of the bar.",
        ],
        "execution": [
            "Push the floor away with your legs, keeping the bar against your body.",
            "Hips and shoulders rise together until you stand tall.",
            "Lower by pushing the hips back first, then bending the knees.",
        ],
        "breathing": "Big breath and brace before the lift; breathe out at the top.",
        "mistakes": ["Rounding the lower back", "Bar drifting away from the legs",
                     "Leaning back at the top"],
        "sources": [],
    },
    "Romanian Deadlift": {
        "mode": "RDL",
        "muscles": "Hamstrings, glutes, lower back",
        "setup": [
            "Stand tall holding the weight in front of your thighs, feet hip-width apart.",
            "Soft bend in the knees that stays the same for the whole rep.",
        ],
        "execution": [
            "Push your hips back and let the weight slide down your legs - this is a hinge, not a squat.",
            "Stop at a strong hamstring stretch or when your back is about level with the floor.",
            "Squeeze your glutes to stand back up straight - do not lean back at the top.",
        ],
        "breathing": "Breathe in on the way down, out as you stand up.",
        "mistakes": ["Going lower than your hamstrings allow (back rounds)",
                     "Bending the knees into a squat", "Leaning back at lockout"],
        "sources": [("FM722", "p. 9-58, straight-leg deadlift")],
    },
    "Hip Thrust": {
        "mode": "HIPTHRUST",
        "muscles": "Glutes, hamstrings",
        "setup": [
            "Upper back against a bench, feet flat and hip-width apart.",
            "Weight across your hips; chin slightly tucked.",
        ],
        "execution": [
            "Drive your hips up until your body is straight from shoulders to knees.",
            "At the top your shins should be vertical (knees about 90 deg).",
            "Squeeze your glutes for a moment, then lower under control.",
        ],
        "breathing": "Breathe out as you drive up, in as you lower.",
        "mistakes": ["Feet too close or too far (shins not vertical)",
                     "Arching the lower back to get higher", "Not reaching full hip extension"],
        "sources": [],
    },
    "Lat Pulldown": {
        "mode": "PULLDOWN",
        "muscles": "Lats (back), biceps, rear shoulders",
        "setup": [
            "Thighs locked under the pad, grip a little wider than shoulders.",
            "Sit tall, chest up, a small lean back at most.",
        ],
        "execution": [
            "Pull the bar to your upper chest by driving your elbows down and back.",
            "Keep the same body angle - do not rock back to move the weight.",
            "Let the bar rise slowly until your arms are straight.",
        ],
        "breathing": "Breathe out as you pull down, in as the bar rises.",
        "mistakes": ["Leaning back more and more to move the bar",
                     "Pulling the bar behind the neck", "Letting the bar yank the arms up"],
        "sources": [("FM722", "p. 6-50 and 6-51, lat pulldown")],
    },
    "T-Bar Row": {
        "mode": "TBAR",
        "muscles": "Mid and upper back, lats, biceps",
        "setup": [
            "Straddle the bar, hinge at the hips until your chest is angled toward the floor.",
            "Flat back, knees soft, grip the handles.",
        ],
        "execution": [
            "Pull the handles toward your chest, squeezing your shoulder blades together.",
            "Keep your chest angle fixed - no standing up to move the weight.",
            "Lower slowly to straight arms.",
        ],
        "breathing": "Breathe out as you pull, in as you lower.",
        "mistakes": ["Rounding the back", "Jerking the torso up to lift the weight",
                     "Shrugging instead of rowing"],
        "sources": [],
    },
    "Leg Extension": {
        "mode": "LEGEXT",
        "muscles": "Thighs (quads)",
        "setup": [
            "Back against the seat, knees lined up with the machine's pivot point.",
            "Pad resting on the front of your ankles; hold the handles to stay seated.",
        ],
        "execution": [
            "Straighten your legs smoothly until they are straight but not locked.",
            "Pause for a moment at the top, squeezing the thighs.",
            "Lower slowly - take longer to lower than to lift.",
        ],
        "breathing": "Breathe out as you lift, in as you lower.",
        "mistakes": ["Kicking up and snapping the knees straight", "Hips lifting off the seat",
                     "Dropping the weight on the way down"],
        "sources": [("FM722", "p. 6-32, straighten legs without locking")],
    },
    "Leg Raises": {
        "mode": "LEGRAISE",
        "muscles": "Lower abs, hip flexors",
        "setup": [
            "Lie on your back, legs straight, hands under your hips or by your sides.",
            "Press your lower back into the floor.",
        ],
        "execution": [
            "Keeping legs straight, raise them until they point up toward the ceiling.",
            "Lower them slowly; stop before your lower back starts to lift off the floor.",
        ],
        "breathing": "Breathe out as you raise, in as you lower.",
        "mistakes": ["Lower back arching off the floor", "Bending the knees",
                     "Dropping the legs quickly"],
        "sources": [("FM722", "p. 6-11 to 6-14, 4 for the core")],
    },
    "Tricep Pushdown": {
        "mode": "PUSHDOWN",
        "muscles": "Triceps",
        "setup": [
            "Stand facing the cable, grip the bar or rope, elbows pinned at your sides.",
            "Slight forward lean, chest up.",
        ],
        "execution": [
            "Push down until your arms are fully straight; only the forearms move.",
            "Squeeze the triceps at the bottom.",
            "Let the handle rise slowly until forearms are about level with the floor.",
        ],
        "breathing": "Breathe out as you push down, in as it rises.",
        "mistakes": ["Elbows drifting forward and away from the body",
                     "Leaning over the bar to push with body weight", "Letting the cable snap back up"],
        "sources": [],
    },
}

MODE_TO_NAME = {g["mode"]: name for name, g in GUIDE.items()}

# Demonstration video for each exercise: the MuscleWiki exercise page (front +
# side videos and written steps). Linked, not embedded - the app opens the
# page in a new tab rather than hotlinking MuscleWiki's video files.
MUSCLEWIKI = "https://musclewiki.com/exercise/"
VIDEO_SLUGS = {
    "Squats": "barbell-squat", "Planks": "forearm-plank", "Tricep Dips": "bench-dips",
    "Pushups": "push-up", "Pullups": "pull-ups", "Russian Twists": "bodyweight-russian-twist",
    "Bicep Curls": "barbell-curl", "Hammer Curls": "dumbbell-hammer-curl",
    "Lateral Raises": "dumbbell-lateral-raise", "Shoulder Press": "dumbbell-overhead-press",
    "Bench Press": "barbell-bench-press", "Inclined Bench Press": "barbell-incline-bench-press",
    "Decline Bench Press": "dumbbell-decline-bench-press", "Chest Fly Machine": "machine-pec-fly",
    "Deadlift": "barbell-deadlift", "Romanian Deadlift": "barbell-romanian-deadlift",
    "Hip Thrust": "barbell-hip-thrust", "Lat Pulldown": "machine-pulldown",
    "T-Bar Row": "landmine-t-bar-rows", "Leg Extension": "machine-leg-extension",
    "Leg Raises": "laying-leg-raises", "Tricep Pushdown": "cable-rope-pushdown",
}


def video_url(name):
    slug = VIDEO_SLUGS.get(name)
    return MUSCLEWIKI + slug if slug else None


# ---------------------------------------------------------------------------
# Live numeric checkpoints - read from the engine's calibrated params (P).
# ---------------------------------------------------------------------------
def _d(v):
    return f"{float(v):.0f} deg"


_CHECKPOINTS = {
    "SQUAT": lambda P: [
        f"Knee angle at the bottom: about {_d(P['TARGET'])} (thighs roughly level with the floor).",
        f"Too deep: knee angle closing past {_d(P['BUF_MIN'])}.",
        f"Upper body lean from vertical: ideally under {_d(P['BACK_PERFECT_MAX'])}; "
        f"over {_d(P['BACK_WARNING_MAX'])} is flagged.",
        f"Knees at least {P['KNEE_WIDTH_RATIO'] * 100:.0f}% as wide apart as the hips.",
    ],
    "PLANK": lambda P: [
        f"Shoulder-hip-knee line: 180 deg is perfectly straight; under {_d(P['HIP_MIN'])} is flagged as sagging.",
        f"Knees straight: knee angle above {_d(P['KNEE_MIN'])}.",
    ],
    "DIP": lambda P: [
        f"Elbow angle at the bottom: about {_d(P['TARGET'])}.",
        f"Too deep: elbow angle below {_d(P['TARGET'] - 10)}.",
    ],
    "PUSHUP": lambda P: [
        f"Elbow angle at the bottom: about {_d(P['TARGET'])}.",
        f"Body line (shoulder-hip-knee) stays above {_d(P['HIP_MIN'])}.",
        f"Upper arm stays within {_d(P['FLARE_MAX'])} of the torso.",
    ],
    "PULLUP": lambda P: [
        f"Elbow angle at the top: about {_d(P['TARGET_TOP'])} (chin over the bar).",
        f"Start each rep from a near-straight arm (above {_d(P['HANG'])}).",
    ],
    "TWIST": lambda P: [
        f"Torso-thigh angle: about {_d(P['TARGET_POSTURE'])} (+/- {P['BUFFER']} deg).",
    ],
    "BICEP": lambda P: [
        f"Elbow angle at the top: about {_d(P['TARGET'])}.",
        f"Elbow stays at your side: upper arm within {_d(P['FLARE_MAX'])} of the torso.",
        f"Arm straightens to above {_d(P['EXTENDED'])} at the bottom.",
    ],
    "HAMMER": lambda P: [
        f"Elbow angle at the top: about {_d(P['TARGET'])}.",
        f"Elbow stays at your side: upper arm within {_d(P['FLARE_MAX'])} of the torso.",
    ],
    "LATERAL": lambda P: [
        f"Arms at shoulder height read about 100-110 deg on camera (the torso line slopes in toward the hips).",
        f"Rep counts once the arm passes {_d(P['TARGET_UP'] - P['BUFFER'])}; too high: above {_d(P['HIGH_MAX'])}.",
        f"Elbows nearly straight: above {_d(P['ELBOW_MIN'])}.",
    ],
    "PRESS": lambda P: [
        f"Start: elbows bent about {_d(P['TARGET_START'])}, weights at shoulder height.",
        f"Top: arms near straight, about {_d(P['TARGET_EXTENSION'])}.",
        f"Torso lean: under {_d(P['BACK_LEAN_MAX'])}.",
        f"Left/right elbow difference: under {_d(P['ASYM_MAX'])}.",
    ],
    "RDL": lambda P: [
        f"Hip angle at the bottom: about {_d(P['HIP_BOTTOM'])}; below {_d(P['HIP_FLOOR'])} is too low.",
        f"Knees stay soft but fairly straight: above {_d(P['KNEE_MIN'])}.",
        f"At the top: stand straight, torso lean under {_d(P['LEAN_BACK_MAX'])}.",
    ],
    "HIPTHRUST": lambda P: [
        f"Hip angle at the top: about {_d(P['HIP_TOP'])} (straight shoulders-to-knees).",
        f"Knee angle at the top: about {_d(P['KNEE_TOP_TARGET'])} (vertical shins).",
    ],
    "PULLDOWN": lambda P: [
        f"Elbow angle at the bottom of the pull: about {_d(P['PULL'])}.",
        f"Torso lean back: under {_d(P['LEAN_MAX'])}.",
    ],
    "LEGEXT": lambda P: [
        f"Knee angle at the top: about {_d(P['TOP'])} - straight but not locked.",
        f"Snapping into lockout: above {_d(P['LOCKOUT_MAX'])}.",
    ],
    "LEGRAISE": lambda P: [
        f"Hip angle at the top: about {_d(P['TOP'])} (legs pointing up).",
        f"Knees straight: above {_d(P['KNEE_MIN'])}.",
    ],
}


# ---------------------------------------------------------------------------
# Which metric shows each loggable fault, and its safe limit.
#   worst: "min" -> the lowest value seen during the fault is the worst one
#          "max" -> the highest value is the worst one
#   limit(P) -> (limit value, human text). None = no meaningful single number
#   (e.g. the press elbow-path checks are in standard-deviation units).
# ---------------------------------------------------------------------------
FAULT_MEASURES = {
    "KNEES CAVING IN! (PUSH OUT)": {
        "metric": "knee_ratio", "worst": "min", "what": "Knee width (as % of hip width)", "pct": True,
        "limit": lambda P: (P["KNEE_WIDTH_RATIO"], f"at least {P['KNEE_WIDTH_RATIO'] * 100:.0f}%"),
    },
    "TOO DEEP (SPINE RISK)": {
        "metric": "leg", "worst": "min", "what": "Knee angle at the bottom",
        "limit": lambda P: (P["BUF_MIN"], f"not below {_d(P['BUF_MIN'])} (target about {_d(P['TARGET'])})"),
    },
    "DANGER: FORWARD LEAN": {
        "metric": "back", "worst": "max", "what": "Upper-body lean from vertical",
        "limit": lambda P: (P["BACK_WARNING_MAX"], f"under {_d(P['BACK_WARNING_MAX'])} (ideal under {_d(P['BACK_PERFECT_MAX'])})"),
    },
    "STRAIGHTEN HIPS": {
        "metric": "hip", "worst": "min", "what": "Shoulder-hip-knee line",
        "limit": lambda P: (P["HIP_MIN"], f"at least {_d(P['HIP_MIN'])} (180 = perfectly straight)"),
    },
    "TOO DEEP (SHOULDER RISK)": {
        "metric": "elbow", "worst": "min", "what": "Elbow angle at the bottom",
        "limit": lambda P: (P["TARGET"] - 10, f"not below {_d(P['TARGET'] - 10)}"),
    },
    "HIPS SAGGING": {
        "metric": "hip", "worst": "min", "what": "Body line (shoulder-hip-knee)",
        "limit": lambda P: (P["HIP_MIN"], f"at least {_d(P['HIP_MIN'])}"),
    },
    "TUCK ELBOWS (DON'T FLARE)": {
        "metric": "flare", "worst": "max", "what": "Upper-arm angle away from the torso",
        "limit": lambda P: (P["FLARE_MAX"], f"under {_d(P['FLARE_MAX'])}"),
    },
    "TUCK ELBOWS IN": {
        "metric": "flare", "worst": "max", "what": "Elbow angle forward of the torso",
        "limit": lambda P: (P["FLARE_MAX"], f"under {_d(P['FLARE_MAX'])}"),
    },
    "TOO HIGH (LOWER ARMS)": {
        "metric": "raise", "worst": "max", "what": "Arm angle from the body",
        "limit": lambda P: (P["HIGH_MAX"], f"under {_d(P['HIGH_MAX'])} (shoulder height reads about 100-110 deg on camera)"),
    },
    "UNEVEN PRESS (BALANCE ARMS)": {
        "metric": "asym", "worst": "max", "what": "Left/right elbow angle difference",
        "limit": lambda P: (P["ASYM_MAX"], f"under {_d(P['ASYM_MAX'])}"),
    },
    "KEEP TORSO UPRIGHT (DON'T LEAN)": {
        "metric": "back", "worst": "max", "what": "Torso lean",
        "limit": lambda P: (P["BACK_LEAN_MAX"], f"under {_d(P['BACK_LEAN_MAX'])}"),
    },
    "TOO LOW (LOWER BACK ROUNDING)": {
        "metric": "hip", "worst": "min", "what": "Hip hinge angle at the bottom",
        "limit": lambda P: (P["HIP_FLOOR"], f"not below {_d(P['HIP_FLOOR'])}"),
    },
    "STAND TALL - DON'T LEAN AT LOCKOUT": {
        "metric": "torso", "worst": "max", "what": "Torso lean at the top",
        "limit": lambda P: (P["LEAN_BACK_MAX"], f"under {_d(P['LEAN_BACK_MAX'])}"),
    },
    "STOP LEANING BACK (LOWER BACK STRAIN)": {
        "metric": "torso", "worst": "max", "what": "Torso lean back",
        "limit": lambda P: (P["LEAN_MAX"], f"under {_d(P['LEAN_MAX'])}"),
    },
    "DON'T SNAP INTO LOCKOUT": {
        "metric": "knee", "worst": "max", "what": "Knee angle at the top",
        "limit": lambda P: (P["LOCKOUT_MAX"], f"under {_d(P['LOCKOUT_MAX'])}"),
    },
}

# A fault that fires on more than this share of frames of the CORRECT reference
# recording is reported as low confidence.
LOW_CONFIDENCE_RATE = 0.10


def _specs():
    import engine  # lazy: building specs reads the golden recordings
    return engine.SPECS


def fault_metric(mode, message):
    """(metric key, worst-direction) for a fault, or (None, None)."""
    m = FAULT_MEASURES.get(message)
    spec = _specs().get(mode)
    if not m or not spec or m["metric"] not in spec.metrics:
        return None, None
    return m["metric"], m["worst"]


# One plain sentence per fault, for readers who don't care about angles.
# {how} becomes "a little" or "much" depending on how far past the limit they went.
PLAIN = {
    "KNEES CAVING IN! (PUSH OUT)": "Your knees came {how} too close together.",
    "TOO DEEP (SPINE RISK)": "You went {how} too low for your lower back.",
    "DANGER: FORWARD LEAN": "Your upper body tipped {how} too far forward.",
    "STRAIGHTEN HIPS": "Your hips dropped {how} too low, out of a straight line.",
    "TOO DEEP (SHOULDER RISK)": "You went {how} too low for your shoulders.",
    "HIPS SAGGING": "Your hips dropped {how} too low, out of a straight line.",
    "TUCK ELBOWS (DON'T FLARE)": "Your elbows pointed {how} too far out to the sides.",
    "TUCK ELBOWS IN": "Your elbow moved {how} too far forward from your side.",
    "TOO HIGH (LOWER ARMS)": "Your arms went {how} too high, above shoulder height.",
    "UNEVEN PRESS (BALANCE ARMS)": "One arm fell {how} too far behind the other.",
    "KEEP TORSO UPRIGHT (DON'T LEAN)": "You leaned {how} too far while pressing.",
    "TOO LOW (LOWER BACK ROUNDING)": "You bent {how} too low to keep your back flat.",
    "STAND TALL - DON'T LEAN AT LOCKOUT": "You leaned {how} too far at the top instead of standing straight.",
    "STOP LEANING BACK (LOWER BACK STRAIN)": "You leaned back {how} too far to move the bar.",
    "DON'T SNAP INTO LOCKOUT": "Your knees snapped {how} too straight at the top.",
}

# Under this many degrees (or percentage points) past the limit = "a little".
SLIGHT_MARGIN = 10


def describe_measurement(mode, message, measured):
    """-> {"what", "value", "limit", "plain"} for the report, or None.
    "plain" is the everyday-language version; the rest are the specifics."""
    m = FAULT_MEASURES.get(message)
    spec = _specs().get(mode)
    if not m or not spec or measured is None:
        return None
    try:
        limit_value, limit_text = m["limit"](spec.params)
    except (KeyError, TypeError):
        return None
    scale = 100 if m.get("pct") else 1
    how = "a little" if abs(measured - limit_value) * scale < SLIGHT_MARGIN else "much"
    value = f"{measured * 100:.0f}%" if m.get("pct") else _d(measured)
    plain = PLAIN.get(message, "").format(how=how) or None
    return {"what": m["what"], "value": value, "limit": limit_text, "plain": plain}


def checkpoints(mode):
    spec = _specs().get(mode)
    fn = _CHECKPOINTS.get(mode)
    if not spec or not fn:
        return []
    try:
        return fn(spec.params)
    except (KeyError, TypeError):
        return []


def source_lines(entry):
    return [f"{SOURCES[k]['short']}, {loc}" for k, loc in entry.get("sources", [])]


def guide_for_mode(mode):
    name = MODE_TO_NAME.get(mode)
    return (name, GUIDE[name]) if name else (None, None)


def guide_payload():
    """JSON for GET /form-guide: {name: {...}}. 'tracked' = the camera checks it live."""
    live = _specs()
    out = {}
    for name, g in GUIDE.items():
        tracked = g["mode"] in live
        out[name] = {
            "mode": g["mode"],
            "tracked": tracked,
            "muscles": g["muscles"],
            "setup": g["setup"],
            "execution": g["execution"],
            "breathing": g["breathing"],
            "mistakes": g["mistakes"],
            "checkpoints": checkpoints(g["mode"]) if tracked else [],
            "sources": source_lines(g),
            "video": video_url(name),
        }
    return out


@lru_cache(maxsize=1)
def reference_false_alarm_rates():
    """{(mode, message): share of frames} - how often each loggable fault fires
    on the exercise's CORRECT golden recording. Computed once, lazily."""
    from calibration import GOLDEN_DIR, read_frames
    from exercise_specs import GOLDEN_CSV
    from spec_framework import analyze

    rates = {}
    for mode, spec in _specs().items():
        csv_name = GOLDEN_CSV.get(mode)
        frames = read_frames(os.path.join(GOLDEN_DIR, csv_name)) if csv_name else []
        if not frames:
            continue
        state, counts = None, {}
        for frame in frames:
            fb, _c, state, _t = analyze(spec, frame, state)
            if fb in MISHAP_EXPLANATIONS:
                counts[fb] = counts.get(fb, 0) + 1
        for msg, n in counts.items():
            rates[(mode, msg)] = n / len(frames)
    return rates


def _validate():
    for name, g in GUIDE.items():
        for key in ("mode", "muscles", "setup", "execution", "breathing", "mistakes", "sources"):
            assert key in g, f"{name}: missing {key}"
        for key, _loc in g["sources"]:
            assert key in SOURCES, f"{name}: unknown source {key}"
        texts = [g["muscles"], g["breathing"], *g["setup"], *g["execution"], *g["mistakes"]]
        assert all(t.isascii() for t in texts), f"{name}: non-ASCII text would break the PDF font"
    assert set(VIDEO_SLUGS) == set(GUIDE), "every exercise needs a MuscleWiki video"
    for msg in FAULT_MEASURES:
        assert msg in MISHAP_EXPLANATIONS, f"FAULT_MEASURES has unknown fault {msg}"


_validate()
