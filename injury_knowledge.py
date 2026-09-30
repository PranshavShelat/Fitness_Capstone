"""Curated injury knowledge: exact fault message (as produced by the form engine)
-> a plain-language explanation, how to fix it, and where every claim comes from.

This dict IS the filter for what counts as a loggable "mishap" - not every
red-coloured engine message is an injury risk (some are just depth/pace
coaching), so only messages present here get logged and reported.

Written for a reader who has never lifted weights:
  * Short sentences. Technical terms are avoided or explained in brackets.
  * No citations or manual page numbers inside the advice - those live in
    "sources" and are printed in small type under each section and in the
    References list, so the report stays readable AND fully traceable.
  * Every explanation only says what its listed sources support. Where no
    specific study exists for a fault, "evidence" is "coaching" and the text
    says so plainly.
  * "prevention" is printed verbatim - it is NOT rewritten by Gemini, so the
    advice a user reads is exactly the advice that was sourced.
  * Plain ASCII only, because the PDF uses fpdf2's core Helvetica font.
"""

# ---------------------------------------------------------------------------
# Sources. "file" is where the document lives in this repo (None = not yet
# downloaded - see knowledge_base/source_pdfs/injury/README.md).
# ---------------------------------------------------------------------------
SOURCES = {
    "FM722": {
        "short": "US Army FM 7-22 (2012)",
        "full": "Headquarters, Department of the Army. FM 7-22: Army Physical Readiness "
                "Training. Washington, DC; October 2012 (incl. Change 1, May 2013).",
        "type": "Government guideline",
        "file": "knowledge_base/source_pdfs/workouts/general_army_fm7-22_physical_readiness_training.pdf",
    },
    "HHS_PAG": {
        "short": "HHS Physical Activity Guidelines (2018)",
        "full": "U.S. Department of Health and Human Services. Physical Activity Guidelines "
                "for Americans, 2nd edition. Washington, DC: HHS; 2018. Chapter 7, Active and Safe.",
        "type": "Government guideline",
        "file": "knowledge_base/source_pdfs/workouts/maintain_hhs_physical_activity_guidelines_2nd_edition.pdf",
    },
    "KOLBER2010": {
        "short": "Kolber et al., J Strength Cond Res (2010)",
        "full": "Kolber MJ, Beekhuizen KS, Cheng MS, Hellman MA. Shoulder injuries attributed "
                "to resistance training: a brief review. J Strength Cond Res. "
                "2010;24(6):1696-1704. doi:10.1519/JSC.0b013e3181dc4330",
        "type": "Peer-reviewed review",
        "file": None,
    },
    "CALLAGHAN2001": {
        "short": "Callaghan & McGill, Clin Biomech (2001)",
        "full": "Callaghan JP, McGill SM. Intervertebral disc herniation: studies on a porcine "
                "model exposed to highly repetitive flexion/extension motion with compressive "
                "force. Clin Biomech. 2001;16(1):28-37. doi:10.1016/S0268-0033(00)00063-2",
        "type": "Peer-reviewed lab study (animal model)",
        "file": None,
    },
    "HEWETT2005": {
        "short": "Hewett et al., Am J Sports Med (2005)",
        "full": "Hewett TE, Myer GD, Ford KR, Heidt RS, Colosimo AJ, McLean SG, van den Bogert AJ, "
                "Paterno MV, Succop P. Biomechanical measures of neuromuscular control and valgus "
                "loading of the knee predict anterior cruciate ligament injury risk in female "
                "athletes: a prospective study. Am J Sports Med. 2005;33(4):492-501. "
                "doi:10.1177/0363546504269591",
        "type": "Peer-reviewed prospective study",
        "file": "knowledge_base/source_pdfs/injury/hewett2005_knee_valgus_acl_risk.pdf",
    },
    "ESCAMILLA1998": {
        "short": "Escamilla et al., Med Sci Sports Exerc (1998)",
        "full": "Escamilla RF, Fleisig GS, Zheng N, Barrentine SW, Wilk KE, Andrews JR. "
                "Biomechanics of the knee during closed kinetic chain and open kinetic chain "
                "exercises. Med Sci Sports Exerc. 1998;30(4):556-569.",
        "type": "Peer-reviewed lab study",
        "file": "knowledge_base/source_pdfs/injury/escamilla1998_knee_biomechanics_open_closed_chain.pdf",
    },
    "SCHOENFELD2010": {
        "short": "Schoenfeld, J Strength Cond Res (2010)",
        "full": "Schoenfeld BJ. Squatting kinematics and kinetics and their application to "
                "exercise performance. J Strength Cond Res. 2010;24(12):3497-3506. "
                "doi:10.1519/JSC.0b013e3181bac2d7 (only page 1 is in the repo - the "
                "cited passage is on it)",
        "type": "Peer-reviewed review",
        "file": "knowledge_base/source_pdfs/injury/schoenfeld2010_squatting_kinematics_kinetics_page1.pdf",
    },
}

# Printed under each fault as "How sure we are: ..." so a reader can tell a
# researched injury risk apart from a technique tip.
EVIDENCE_LABELS = {
    "research": "Strong - backed by research studies and an official training manual",
    "guideline": "Based on an official training manual (US Army)",
    "coaching": "Technique tip - good form, but no study links this exact mistake to injury",
}

# Reusable corrective exercises, described step by step (all from FM 7-22;
# the page numbers are in each fault's sources).
_HIP = (
    "Side-lying leg raises. Lie on your side with your legs straight and lift your top leg "
    "about 15-20 cm (6-8 inches), then lower it slowly. Do 5 slow reps on each side before "
    "leg workouts. This strengthens the muscles on the outside of your hip that keep your "
    "knees pointing forward."
)
_CORE = (
    "Two core holds. Side plank: lie on your side, prop yourself up on your elbow and lift "
    "your hips until your body is straight. Glute bridge: lie on your back with knees bent "
    "and lift your hips until your body is straight from shoulders to knees. Hold each for "
    "up to 60 seconds; if your form slips, rest a few seconds and carry on. These build the "
    "muscles that protect your lower back."
)
_SHOULDER = (
    "Shoulder raises lying face down, no weights. Lie on your stomach and lift both arms "
    "8-15 cm (3-6 inches) off the floor, first straight above your head (like the letter I), "
    "then straight out to the sides (like a T). Do 5 slow reps of each. This strengthens the "
    "small muscles that keep your shoulder joint steady."
)
_PROGRESS = (
    "Add weight in small steps, and only after a whole workout of good reps. Injuries are "
    "most likely when you jump far beyond what your body is used to."
)

_SRC_HIP = ("FM722", "p. 6-16, hip stability drill")
_SRC_CORE = ("FM722", "p. 6-11 to 6-14, 4 for the core")
_SRC_SHOULDER = ("FM722", "p. 6-25 to 6-27, shoulder stability drill")
_SRC_PROGRESS = ("HHS_PAG", "p. 90, increase activity gradually")


MISHAP_EXPLANATIONS = {
    # ------------------------------------------------------------------ SQUAT
    "KNEES CAVING IN! (PUSH OUT)": {
        "label": "Knees Caving In",
        "evidence": "research",
        "explanation": (
            "Your knees moved inward, toward each other, as you squatted. This puts extra strain "
            "on the inside of your knees instead of letting your hips and thighs share the work. "
            "In a study that followed 205 female athletes, the ones whose knees caved in more "
            "when landing from jumps were the ones who later tore a knee ligament (the ACL). "
            "That study looked at jumping, not squats, but it is the same knee movement."
        ),
        "prevention": {
            "fix": "Push your knees out so they point the same way as your toes, all the way down "
                   "and back up. If they still cave in, use less weight for now.",
            "drill": _HIP,
            "progression": _PROGRESS,
        },
        "sources": [
            ("HEWETT2005", "study of jump landings"),
            ("FM722", "p. 6-109 and 8-8, knee position"),
            _SRC_HIP, _SRC_PROGRESS,
        ],
    },
    "TOO DEEP (SPINE RISK)": {
        "label": "Squatting Too Deep (Lower Back Rounding)",
        "evidence": "research",
        "explanation": (
            "You went so low that your hips tucked under at the bottom and your lower back "
            "rounded. Bending your spine again and again while it carries weight is how the discs "
            "in your back (the cushions between the bones) can get injured. Lab studies on spines "
            "have shown that this kind of repeated bending under load can damage those discs."
        ),
        "prevention": {
            "fix": "Only go down as far as you can while keeping your lower back flat. For most "
                   "people that is around where the thighs are level with the floor. Tighten your "
                   "stomach muscles before each rep and keep your chest up.",
            "drill": _CORE,
            "progression": "Practise your full depth with a light weight first, and only go lower "
                           "once your back stays flat. " + _PROGRESS,
        },
        "sources": [
            ("CALLAGHAN2001", "lab study on spines (animal model)"),
            ("SCHOENFELD2010", "squat injuries from poor technique"),
            ("FM722", "p. 9-56, squat to thighs level with the floor"),
            _SRC_CORE, _SRC_PROGRESS,
        ],
    },
    "DANGER: FORWARD LEAN": {
        "label": "Leaning Too Far Forward (Squat)",
        "evidence": "guideline",
        "explanation": (
            "Your chest dropped and your upper body tipped too far forward, so your hips rose "
            "faster than your shoulders. That moves the work away from your legs and onto your "
            "lower back. Official training guidance allows only a slight forward lean, with your "
            "back kept straight."
        ),
        "prevention": {
            "fix": "Keep your chest up and your eyes looking straight ahead, and push your hips "
                   "and shoulders up at the same speed.",
            "drill": _CORE + " Also stretch the front of your hips: step one foot far back into "
                     "a lunge and hold for 20-30 seconds on each side. Tight hips pull your "
                     "body forward.",
            "progression": "Use less weight until your upper body stays at the same angle from "
                           "the bottom of the squat to the top.",
        },
        "sources": [
            ("FM722", "p. 8-8, squat check points; App. C, posture"),
            ("FM722", "p. 6-109, hip stretch"),
            _SRC_CORE,
        ],
    },

    # ------------------------------------------------------------------ PLANK
    "STRAIGHTEN HIPS": {
        "label": "Hips Sagging (Plank)",
        "evidence": "guideline",
        "explanation": (
            "Your hips dropped below a straight line from your shoulders to your feet. When this "
            "happens, your stomach muscles stop doing the work and your lower back sags and "
            "takes the strain instead."
        ),
        "prevention": {
            "fix": "Squeeze your bottom and pull your belly button in toward your spine, keeping "
                   "your body in one straight line from head to heels.",
            "drill": "When your hips start to drop, stop, rest for 3-5 seconds, then start again, "
                     "until you have held for 60 seconds in total. Side planks and glute bridges "
                     "build the same muscles.",
            "progression": "Only hold for longer while your body stays straight. A short, "
                           "straight plank is better than a long, sagging one.",
        },
        "sources": [_SRC_CORE],
    },

    # ------------------------------------------------------------------ DIP
    "TOO DEEP (SHOULDER RISK)": {
        "label": "Going Too Low on Dips",
        "evidence": "research",
        "explanation": (
            "You lowered yourself further than your shoulders can safely support, so the front "
            "of your shoulder was stretched while holding your whole body weight. The shoulder "
            "is the body part most often injured in weight training: a review found up to 36% "
            "of weight-training injuries happen there, often because of poor technique."
        ),
        "prevention": {
            "fix": "Lower yourself only until your upper arms are about level with the floor, then "
                   "push back up. Keep your shoulders down and back, not hunched forward.",
            "drill": _SHOULDER,
            "progression": "If you can't control the bottom of the dip, start with easier versions, "
                           "such as dips with your feet on the floor or an assisted dip machine. "
                           + _PROGRESS,
        },
        "sources": [
            ("KOLBER2010", "review of shoulder injuries in weight training"),
            ("FM722", "p. 6-94, upper arms level with the floor"),
            _SRC_SHOULDER, _SRC_PROGRESS,
        ],
    },

    # ------------------------------------------------------------------ PUSH-UP
    "HIPS SAGGING": {
        "label": "Hips Sagging (Push-up)",
        "evidence": "guideline",
        "explanation": (
            "Your hips dropped during the push-up, so your body sagged in the middle. Your lower "
            "back then takes the strain that your stomach muscles should be carrying. Official "
            "push-up guidance says your body should not sag at any point."
        ),
        "prevention": {
            "fix": "Tighten your stomach and squeeze your bottom before the first rep, and keep "
                   "your body in one straight line from head to heels.",
            "drill": "If you can't keep your body straight, do push-ups from your knees until you "
                     "can, and add side planks and glute bridges to strengthen your core.",
            "progression": "Go back to full push-ups once you can do a whole set from your knees "
                           "without sagging.",
        },
        "sources": [("FM722", "p. 6-94, push-up check points"), _SRC_CORE],
    },
    "TUCK ELBOWS (DON'T FLARE)": {
        "label": "Elbows Flaring Out (Push-up)",
        "evidence": "guideline",
        "explanation": (
            "Your elbows pointed out to the sides as you lowered yourself, instead of staying "
            "close to your body. This puts more strain on the front of your shoulders, the area "
            "most often injured in weight training, where poor technique is a known cause."
        ),
        "prevention": {
            "fix": "Place your hands directly under your shoulders. As you lower, keep your elbows "
                   "pointing back and your upper arms close to your sides.",
            "drill": _SHOULDER,
            "progression": "If your elbows start to flare as you get tired, stop the set there. It "
                           "usually happens in the last few reps.",
        },
        "sources": [
            ("FM722", "p. 6-94, push-up check points"),
            ("KOLBER2010", "technique and shoulder injuries"),
            _SRC_SHOULDER,
        ],
    },

    # ------------------------------------------------------------------ CURLS
    "TUCK ELBOWS IN": {
        "label": "Elbow Moving Forward (Curl)",
        "evidence": "coaching",
        "explanation": (
            "Your elbow moved forward and away from your side while you curled, so your shoulder "
            "started helping to lift the weight. This mainly makes the exercise less effective "
            "for your arm, and puts some load on your shoulder that it doesn't need to carry. No "
            "study links this exact mistake to injury, so treat it as a technique tip."
        ),
        "prevention": {
            "fix": "Keep your elbows pinned to your sides and move only your forearms. Use a weight "
                   "you can lift without swinging.",
            "drill": "Curl slowly and under control, without leaning back to help lift the weight.",
            "progression": "If you have to swing your body or move your elbows to finish a rep, the "
                           "weight is too heavy. Lower it until every rep is clean.",
        },
        "sources": [
            ("FM722", "p. 6-62, biceps curl"),
            ("KOLBER2010", "shoulder injuries in weight training"),
        ],
    },

    # ------------------------------------------------------------------ LATERAL RAISE
    "TOO HIGH (LOWER ARMS)": {
        "label": "Arms Raised Too High (Lateral Raise)",
        "evidence": "guideline",
        "explanation": (
            "You lifted your arms above shoulder height. Official training guidance says to stop "
            "when your arms are level with the floor. Lifting weights out to the side above that "
            "height squeezes the space inside the shoulder joint, which is commonly linked to "
            "painful shoulder pinching (called impingement)."
        ),
        "prevention": {
            "fix": "Stop when your arms are level with the floor, keep a slight bend in your elbows, "
                   "and lead with your elbows rather than your hands.",
            "drill": _SHOULDER,
            "progression": "Use light dumbbells. If you have to swing or shrug your shoulders to "
                           "lift them, they are too heavy.",
        },
        "sources": [
            ("FM722", "p. 6-54, lateral raise"),
            ("KOLBER2010", "shoulder injuries in weight training"),
            _SRC_SHOULDER,
        ],
    },

    # ------------------------------------------------------------------ SHOULDER PRESS
    "UNEVEN PRESS (BALANCE ARMS)": {
        "label": "One Arm Lagging (Shoulder Press)",
        "evidence": "research",
        "explanation": (
            "One arm was behind the other as you pressed, so one side did more of the work and "
            "your body shifted to make up for it. Research on weight-training injuries lists "
            "uneven strength between the two sides as one of the things that makes shoulder "
            "injuries more likely."
        ),
        "prevention": {
            "fix": "Press both arms up at the same speed and finish together. If one side always "
                   "lags, it is the weaker side, so let it set the pace.",
            "drill": "Train each arm on its own with one-arm shoulder presses using a light weight. "
                     "Also: " + _SHOULDER,
            "progression": "Pick a weight your weaker arm can handle for the whole set.",
        },
        "sources": [
            ("KOLBER2010", "uneven strength as a risk factor"),
            ("FM722", "p. 6-47 to 6-49, shoulder press and one-arm version"),
            _SRC_SHOULDER,
        ],
    },
    "DON'T FLARE ELBOWS (PRESS STRAIGHT UP)": {
        "label": "Elbows Flaring Out Too Early (Shoulder Press)",
        "evidence": "guideline",
        "explanation": (
            "Your elbows swung out to the sides before your arms had straightened, so your "
            "shoulders held the weight out wide instead of pushing it straight up. Part of the "
            "press turns into a side raise with a heavy weight, which is harder on the shoulders. "
            "The standard way is to start with your hands above your shoulders and push "
            "straight up."
        ),
        "prevention": {
            "fix": "Keep your forearms upright, with your wrists directly above your elbows, and "
                   "push the weight in a straight line up over your shoulders.",
            "drill": _SHOULDER,
            "progression": "Use less weight until it travels straight up on every rep. " + _PROGRESS,
        },
        "sources": [
            ("FM722", "p. 6-47, shoulder press"),
            ("KOLBER2010", "technique and shoulder injuries"),
            _SRC_SHOULDER, _SRC_PROGRESS,
        ],
    },
    "ELBOWS TOO FAR FORWARD (ROTATE BACK)": {
        "label": "Elbows Too Far Forward (Shoulder Press)",
        "evidence": "coaching",
        "explanation": (
            "Your elbows stayed out in front of your body as you pressed, so part of the movement "
            "became a front raise and the front of your shoulders took extra strain. This is a "
            "technique tip: no study links this exact mistake to injury, but the shoulder is the "
            "most commonly injured area in weight training."
        ),
        "prevention": {
            "fix": "Start with your elbows just in front of your body, and press so the weight ends "
                   "up directly above your shoulders, not in front of your face.",
            "drill": _SHOULDER,
            "progression": _PROGRESS,
        },
        "sources": [
            ("FM722", "p. 6-47, shoulder press"),
            ("KOLBER2010", "shoulder injuries in weight training"),
            _SRC_SHOULDER, _SRC_PROGRESS,
        ],
    },
    "ELBOWS TOO FAR BACK (BRING FORWARD SLIGHTLY)": {
        "label": "Elbows Too Far Back (Shoulder Press)",
        "evidence": "coaching",
        "explanation": (
            "Your elbows went further behind your body than the press needs, which twists your "
            "shoulders into an extreme position at the bottom of each rep. This is a technique "
            "tip: no study links this exact mistake to injury, but it loads the shoulder at the "
            "very end of its range, and the shoulder is the most commonly injured area in "
            "weight training."
        ),
        "prevention": {
            "fix": "Keep your elbows slightly in front of your body at the bottom of the press, "
                   "never pulled back behind it.",
            "drill": _SHOULDER,
            "progression": _PROGRESS,
        },
        "sources": [
            ("FM722", "p. 6-47, shoulder press"),
            ("KOLBER2010", "shoulder injuries in weight training"),
            _SRC_SHOULDER, _SRC_PROGRESS,
        ],
    },
    "KEEP TORSO UPRIGHT (DON'T LEAN)": {
        "label": "Leaning During the Shoulder Press",
        "evidence": "guideline",
        "explanation": (
            "Your upper body tilted while you pressed, so the weight moved away from being over "
            "your body and your lower back had to hold it. Official training guidance keeps your "
            "back straight and your stomach muscles tight during the press, to keep your body "
            "stable."
        ),
        "prevention": {
            "fix": "Tighten your stomach, keep your ribs down, and keep your head, shoulders and "
                   "hips in one line (or your back flat against the bench).",
            "drill": _CORE,
            "progression": "If you have to lean to finish a rep, the weight is too heavy. " + _PROGRESS,
        },
        "sources": [
            ("FM722", "p. 6-47 and 9-66, shoulder press"),
            _SRC_CORE, _SRC_PROGRESS,
        ],
    },
    "KEEP WRISTS ABOVE ELBOWS": {
        "label": "Wrists Dropping Below Elbows (Shoulder Press)",
        "evidence": "guideline",
        "explanation": (
            "Your wrists dropped to or below your elbows, so your forearms weren't pushing "
            "straight up under the weight. Your shoulders then hold the weight from a weak "
            "position, and it is harder to control. The standard setup is a right angle "
            "(90 degrees) at the elbow, with your hands directly above your shoulders."
        ),
        "prevention": {
            "fix": "Keep your forearms upright, with your wrists directly above your elbows, from "
                   "the bottom of the rep to the top.",
            "drill": _SHOULDER,
            "progression": _PROGRESS,
        },
        "sources": [("FM722", "p. 6-47, shoulder press"), _SRC_SHOULDER, _SRC_PROGRESS],
    },

    # ------------------------------------------------------------------ ROMANIAN DEADLIFT
    "TOO LOW (LOWER BACK ROUNDING)": {
        "label": "Back Rounding (Romanian Deadlift)",
        "evidence": "research",
        "explanation": (
            "You bent forward further than the backs of your thighs (your hamstrings) could "
            "stretch, so your hips tucked under and your lower back rounded while holding the "
            "weight. Bending your spine again and again under load is a known way to injure the "
            "discs in your back; lab studies on spines have shown it. The standard way stops when "
            "your back is flat and level with the floor."
        ),
        "prevention": {
            "fix": "Push your hips back and stop when you feel a strong stretch in the backs of your "
                   "thighs, or when your back is about level with the floor, whichever comes first. "
                   "Keep your back flat and your head in line with your spine.",
            "drill": "Practise the movement slowly with no weight until it feels natural. Also: " + _CORE,
            "progression": "Only go lower once your back stays flat all the way down. " + _PROGRESS,
        },
        "sources": [
            ("CALLAGHAN2001", "lab study on spines (animal model)"),
            ("FM722", "p. 9-58, straight-leg deadlift"),
            _SRC_CORE, _SRC_PROGRESS,
        ],
    },
    "STAND TALL - DON'T LEAN AT LOCKOUT": {
        "label": "Not Standing Straight at the Top (Romanian Deadlift)",
        "evidence": "guideline",
        "explanation": (
            "At the top of the lift, your body was still tilted instead of finishing upright. "
            "Leaning back to finish arches your lower back under the weight, and staying tipped "
            "forward leaves your lower back holding the weight instead of your hip muscles. "
            "Official guidance notes that good body alignment lowers injury risk, while poor "
            "alignment raises it."
        ),
        "prevention": {
            "fix": "Finish each rep by squeezing your bottom and standing straight: shoulders over "
                   "hips, ribs down, no leaning back.",
            "drill": _CORE,
            "progression": _PROGRESS,
        },
        "sources": [("FM722", "App. C, posture and body mechanics"), _SRC_CORE, _SRC_PROGRESS],
    },

    # ------------------------------------------------------------------ LAT PULLDOWN
    "STOP LEANING BACK (LOWER BACK STRAIN)": {
        "label": "Leaning Back (Lat Pulldown)",
        "evidence": "guideline",
        "explanation": (
            "You leaned back more and more as you pulled, so your lower back and body weight were "
            "moving the bar instead of your back muscles. Official training guidance keeps your "
            "upper body upright and warns against jerking or leaning back to move the bar."
        ),
        "prevention": {
            "fix": "Sit tall with your chest up and, at most, a small lean that doesn't change. Pull "
                   "the bar to your upper chest by driving your elbows down, not by rocking back.",
            "drill": "Straight-arm pulldowns: keep your arms straight and pull the bar down toward "
                     "your thighs using only your back muscles. This teaches you to pull with your "
                     "back instead of your body weight.",
            "progression": "If you have to rock back to move the weight, lower it.",
        },
        "sources": [("FM722", "p. 6-50 and 6-51, lat pulldown")],
    },

    # ------------------------------------------------------------------ LEG EXTENSION
    "DON'T SNAP INTO LOCKOUT": {
        "label": "Snapping Knees Straight (Leg Extension)",
        "evidence": "research",
        "explanation": (
            "You kicked your legs up hard and snapped your knees straight at the top, so "
            "momentum finished the rep instead of your thigh muscles, and your knee joint was "
            "jolted into its end position under weight. Official guidance straightens the legs "
            "fully but without locking them, and lowers them slowly. Research on this exercise "
            "found that near the fully straight position it pulls on the knee's main ligament "
            "(the ACL), and that the pressure behind the kneecap is highest in the middle of "
            "the movement, so moving slowly through the whole range matters."
        ),
        "prevention": {
            "fix": "Straighten your legs slowly until they are straight but not locked, pause for a "
                   "moment, then lower them slowly.",
            "drill": "Practise with a light weight: lift slowly, stop just before your knees lock, "
                     "hold for a moment, and lower slowly, until that pace feels natural.",
            "progression": "Choose a weight you can lower more slowly than you lift. " + _PROGRESS,
        },
        "sources": [
            ("FM722", "p. 6-32, straighten legs without locking"),
            ("ESCAMILLA1998", "ACL tension near full extension; kneecap pressure mid-range"),
            _SRC_PROGRESS,
        ],
    },
}


# Shown once per report, after the per-fault sections. Every line is sourced.
GENERAL_PREVENTION = [
    ("Increase weight gradually. Injuries are most likely when you jump far beyond what your "
     "body is used to, so make small increases and give your body time to adapt.",
     "HHS_PAG", "p. 90"),
    ("Warm up before lifting by doing each exercise with a lighter weight first.",
     "HHS_PAG", "p. 91"),
    ("More is not always better. If soreness and tiredness never fully go away and your "
     "performance keeps dropping, you may be overtraining. Rest, sleep and good food will help "
     "you improve more than training harder.", "FM722", "p. 5-3"),
    ("If you have hurt a body part before, it is more likely to get hurt again, so build that "
     "area up more slowly.", "HHS_PAG", "p. 89 and 91"),
]


def _validate():
    """Fail fast at import if a fault references a source that doesn't exist, so a
    typo can never reach a PDF as a dangling citation."""
    for msg, info in MISHAP_EXPLANATIONS.items():
        assert info["evidence"] in EVIDENCE_LABELS, msg
        for key, _loc in info["sources"]:
            assert key in SOURCES, f"{msg}: unknown source {key}"
        assert all(info["prevention"].get(k) for k in ("fix", "drill", "progression")), msg
        for text in [info["label"], info["explanation"], *info["prevention"].values()]:
            assert text.isascii(), f"{msg}: non-ASCII text would break the PDF font"
    for _text, key, _loc in GENERAL_PREVENTION:
        assert key in SOURCES, key


_validate()
