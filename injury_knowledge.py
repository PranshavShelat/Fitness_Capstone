# Curated lookup: exact fault message (as produced by engine.py) -> what it means.
# This dict IS the filter for what counts as a loggable "mishap" - not every
# red-colored engine.py message is an injury risk (some are just depth/pace
# coaching), so only messages present here get logged and reported.
#
# "image" is a public-domain anatomical reference plate in assets/anatomy/
# (Gray's Anatomy, 1918 - pre-1931, public domain), and "region" is the
# (x0, y0, x1, y1) bounding box - as fractions of that image's width/height -
# to circle in red on the report diagram for that specific fault.
MISHAP_EXPLANATIONS = {
    "KNEES CAVING IN! (PUSH OUT)": {
        "label": "Knee Valgus",
        "explanation": (
            "The knees are collapsing inward (valgus) under load during the squat. "
            "This shifts stress onto the medial knee structures, particularly the ACL "
            "and meniscus, and is one of the most common mechanisms behind squat-related "
            "knee injuries, especially under repeated loading."
        ),
        "image": "knee.png",
        "region": (0.12, 0.36, 0.88, 0.76),
    },
    "TOO DEEP (SPINE RISK)": {
        "label": "Excessive Squat Depth",
        "explanation": (
            "The squat depth has passed the point where the pelvis typically starts to "
            "tuck under (posterior pelvic tilt), which flexes the lower spine under load. "
            "Loaded lumbar flexion repeated over many reps is linked to intervertebral "
            "disc strain."
        ),
        "image": "spine.png",
        "region": (0.12, 0.60, 0.88, 0.83),
    },
    "DANGER: FORWARD LEAN": {
        "label": "Excessive Forward Lean",
        "explanation": (
            "The torso is leaning too far forward relative to the hips during the squat. "
            "This shifts load off the legs and onto the lower back, increasing shear "
            "force on the lumbar spine, particularly under a loaded bar."
        ),
        "image": "spine.png",
        "region": (0.12, 0.60, 0.88, 0.83),
    },
    "STRAIGHTEN HIPS": {
        "label": "Hip Sag",
        "explanation": (
            "The hips are sagging below a straight line during the plank. This forces the "
            "lower back into hyperextension to hold the position, loading the lumbar "
            "facet joints instead of the core."
        ),
        "image": "spine.png",
        "region": (0.12, 0.60, 0.88, 0.83),
    },
    "TOO DEEP (SHOULDER RISK)": {
        "label": "Excessive Dip Depth",
        "explanation": (
            "The dip has gone below the point where the shoulder joint is well supported. "
            "Past this depth, the humeral head moves into a position associated with "
            "anterior shoulder instability and impingement, especially with repeated reps."
        ),
        "image": "shoulder.png",
        "region": (0.35, 0.15, 0.78, 0.68),
    },
    "HIPS SAGGING": {
        "label": "Hip Sag",
        "explanation": (
            "The hips are dropping below a straight line during the pushup. As with a "
            "sagging plank, this pushes the lower back into hyperextension, loading the "
            "lumbar spine instead of the core and shoulders."
        ),
        "image": "spine.png",
        "region": (0.12, 0.60, 0.88, 0.83),
    },
    "TUCK ELBOWS (DON'T FLARE)": {
        "label": "Elbow Flare",
        "explanation": (
            "The elbows are flaring out wide from the torso during the pushup. This "
            "rotates the shoulder into a position linked with subacromial impingement, "
            "particularly under repeated reps or fatigue."
        ),
        "image": "shoulder.png",
        "region": (0.35, 0.15, 0.78, 0.68),
    },
    "TUCK ELBOWS IN": {
        "label": "Elbow Flare",
        "explanation": (
            "The elbow is drifting away from the torso during the curl. This shifts load "
            "onto the front of the shoulder joint rather than isolating the arm, and over "
            "many reps is associated with anterior shoulder strain."
        ),
        "image": "shoulder.png",
        "region": (0.35, 0.15, 0.78, 0.68),
    },
    "TOO HIGH (LOWER ARMS)": {
        "label": "Arms Raised Too High",
        "explanation": (
            "The arms have been raised above shoulder height during the lateral raise. "
            "Past this point the space under the acromion narrows, which is a well-known "
            "mechanism for shoulder impingement, especially with added weight."
        ),
        "image": "shoulder.png",
        "region": (0.45, 0.10, 0.90, 0.45),
    },
    "UNEVEN PRESS (BALANCE ARMS)": {
        "label": "Uneven Press",
        "explanation": (
            "One arm is significantly behind the other during the press, meaning the load "
            "is not being shared evenly. This asymmetric loading can strain the shoulder "
            "and spine on the side compensating for the imbalance."
        ),
        "image": "shoulder.png",
        "region": (0.35, 0.15, 0.78, 0.68),
    },
    "ELBOWS TOO FAR FORWARD (ROTATE BACK)": {
        "label": "Elbows Drifting Forward",
        "explanation": (
            "The elbows stayed out in front of the body instead of rotating back "
            "into line with the shoulders as the arms pressed up. This turns the "
            "movement into more of a front raise than a true overhead press, putting "
            "extra strain on the front of the shoulder joint and reducing the "
            "stability that a properly rotated shoulder gives the joint under load."
        ),
        "image": "shoulder.png",
        "region": (0.35, 0.15, 0.78, 0.68),
    },
    "ELBOWS TOO FAR BACK (BRING FORWARD SLIGHTLY)": {
        "label": "Elbows Drifting Too Far Back",
        "explanation": (
            "The elbows swung further behind the body than a correct press ever needs, "
            "pushing the shoulder into an extreme, over-rotated position - similar to the "
            "risky 'behind the neck' press style. This overstretches the front of the "
            "shoulder capsule and can pinch tendons under the shoulder blade, raising the "
            "risk of shoulder instability and impingement over repeated reps."
        ),
        "image": "shoulder.png",
        "region": (0.35, 0.15, 0.78, 0.68),
    },
    "KEEP TORSO UPRIGHT (DON'T LEAN)": {
        "label": "Forward Torso Lean",
        "explanation": (
            "The torso leaned forward, bringing the shoulders out in front of the hips "
            "during the press. This turns part of the movement into a forward push rather "
            "than a vertical one, shifting load onto the lower back and reducing shoulder "
            "stability - both of which raise the risk of strain, especially under load or "
            "with heavier weight."
        ),
        "image": "spine.png",
        "region": (0.12, 0.60, 0.88, 0.83),
    },
    "KEEP WRISTS ABOVE ELBOWS": {
        "label": "Inverted Arm Position",
        "explanation": (
            "The wrists dropped to or below elbow height during the press - a 'chicken "
            "wing' position where the arm isn't actually driving the load upward. This "
            "puts the shoulder in a mechanically weak, unstable position and increases "
            "the chance of losing control of the weight, which is a real drop/injury "
            "risk under load."
        ),
        "image": "shoulder.png",
        "region": (0.35, 0.15, 0.78, 0.68),
    },
}
