import mediapipe as mp

PoseLandmark = mp.solutions.pose.PoseLandmark

# Curated lookup: exact fault message (as produced by engine.py) -> what it means.
# This dict IS the filter for what counts as a loggable "mishap" - not every
# red-colored engine.py message is an injury risk (some are just depth/pace
# coaching), so only messages present here get logged and reported.
#
# "highlight" lists which joints get circled/labeled on the report's stick-figure
# diagram for that fault.
MISHAP_EXPLANATIONS = {
    "KNEES CAVING IN! (PUSH OUT)": {
        "label": "Knee Valgus",
        "explanation": (
            "The knees are collapsing inward (valgus) under load during the squat. "
            "This shifts stress onto the medial knee structures, particularly the ACL "
            "and meniscus, and is one of the most common mechanisms behind squat-related "
            "knee injuries, especially under repeated loading."
        ),
        "highlight": [
            PoseLandmark.LEFT_HIP, PoseLandmark.RIGHT_HIP,
            PoseLandmark.LEFT_KNEE, PoseLandmark.RIGHT_KNEE,
        ],
    },
    "TOO DEEP (SPINE RISK)": {
        "label": "Excessive Squat Depth",
        "explanation": (
            "The squat depth has passed the point where the pelvis typically starts to "
            "tuck under (posterior pelvic tilt), which flexes the lower spine under load. "
            "Loaded lumbar flexion repeated over many reps is linked to intervertebral "
            "disc strain."
        ),
        "highlight": [
            PoseLandmark.LEFT_SHOULDER, PoseLandmark.RIGHT_SHOULDER,
            PoseLandmark.LEFT_HIP, PoseLandmark.RIGHT_HIP,
        ],
    },
    "DANGER: FORWARD LEAN": {
        "label": "Excessive Forward Lean",
        "explanation": (
            "The torso is leaning too far forward relative to the hips during the squat. "
            "This shifts load off the legs and onto the lower back, increasing shear "
            "force on the lumbar spine, particularly under a loaded bar."
        ),
        "highlight": [PoseLandmark.RIGHT_SHOULDER, PoseLandmark.RIGHT_HIP],
    },
    "STRAIGHTEN HIPS": {
        "label": "Hip Sag",
        "explanation": (
            "The hips are sagging below a straight line during the plank. This forces the "
            "lower back into hyperextension to hold the position, loading the lumbar "
            "facet joints instead of the core."
        ),
        "highlight": [PoseLandmark.RIGHT_SHOULDER, PoseLandmark.RIGHT_HIP, PoseLandmark.RIGHT_KNEE],
    },
    "TOO DEEP (SHOULDER RISK)": {
        "label": "Excessive Dip Depth",
        "explanation": (
            "The dip has gone below the point where the shoulder joint is well supported. "
            "Past this depth, the humeral head moves into a position associated with "
            "anterior shoulder instability and impingement, especially with repeated reps."
        ),
        "highlight": [PoseLandmark.RIGHT_SHOULDER, PoseLandmark.RIGHT_ELBOW, PoseLandmark.RIGHT_WRIST],
    },
    "HIPS SAGGING": {
        "label": "Hip Sag",
        "explanation": (
            "The hips are dropping below a straight line during the pushup. As with a "
            "sagging plank, this pushes the lower back into hyperextension, loading the "
            "lumbar spine instead of the core and shoulders."
        ),
        "highlight": [PoseLandmark.RIGHT_SHOULDER, PoseLandmark.RIGHT_HIP, PoseLandmark.RIGHT_KNEE],
    },
    "TUCK ELBOWS (DON'T FLARE)": {
        "label": "Elbow Flare",
        "explanation": (
            "The elbows are flaring out wide from the torso during the pushup. This "
            "rotates the shoulder into a position linked with subacromial impingement, "
            "particularly under repeated reps or fatigue."
        ),
        "highlight": [PoseLandmark.RIGHT_HIP, PoseLandmark.RIGHT_SHOULDER, PoseLandmark.RIGHT_ELBOW],
    },
    "TUCK ELBOWS IN": {
        "label": "Elbow Flare",
        "explanation": (
            "The elbow is drifting away from the torso during the curl. This shifts load "
            "onto the front of the shoulder joint rather than isolating the arm, and over "
            "many reps is associated with anterior shoulder strain."
        ),
        "highlight": [PoseLandmark.RIGHT_HIP, PoseLandmark.RIGHT_SHOULDER, PoseLandmark.RIGHT_ELBOW],
    },
    "TOO HIGH (LOWER ARMS)": {
        "label": "Arms Raised Too High",
        "explanation": (
            "The arms have been raised above shoulder height during the lateral raise. "
            "Past this point the space under the acromion narrows, which is a well-known "
            "mechanism for shoulder impingement, especially with added weight."
        ),
        "highlight": [
            PoseLandmark.RIGHT_HIP, PoseLandmark.RIGHT_SHOULDER,
            PoseLandmark.RIGHT_ELBOW, PoseLandmark.RIGHT_WRIST,
        ],
    },
    "UNEVEN PRESS (BALANCE ARMS)": {
        "label": "Uneven Press",
        "explanation": (
            "One arm is significantly behind the other during the press, meaning the load "
            "is not being shared evenly. This asymmetric loading can strain the shoulder "
            "and spine on the side compensating for the imbalance."
        ),
        "highlight": [
            PoseLandmark.LEFT_SHOULDER, PoseLandmark.LEFT_ELBOW, PoseLandmark.LEFT_WRIST,
            PoseLandmark.RIGHT_SHOULDER, PoseLandmark.RIGHT_ELBOW, PoseLandmark.RIGHT_WRIST,
        ],
    },
}
