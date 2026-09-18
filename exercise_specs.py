"""All 22 exercises, as data.

Each spec declares only what is specific to that movement: which joints to
measure, what counts as a rep, and an ORDERED list of fault rules. Everything
else - side selection, visibility gating, rep state, fault priority, telemetry
formatting - lives once in spec_framework.analyze().

Rule ordering is the safety-critical part of a spec. The first matching rule
wins, so anything that carries genuine injury risk is listed above anything that
is merely coaching depth or tempo; otherwise a dangerous position gets masked by
a benign "go lower" message on the same frame.
"""
from calibration import build_phase_reference, calibrate_angle, measure_visibility
from pose_math import (
    angle, asymmetry, bilateral_angle, bilateral_y_diff, binned_deviation,
    calculate_angle, gap, lean, midpoint_lean, running_extreme, side_angle,
    smoothed, visibility, width_ratio, x_gap, y_diff, z_diff,
)
from spec_framework import GREEN, ORANGE, RED, WHITE, YELLOW, ExerciseSpec, RepPhase, Rule

# Which golden_dataset recording each exercise is calibrated from and validated
# against. Kept as one map so the test suite, the calibration report and the
# specs themselves cannot drift apart.
GOLDEN_CSV = {
    "SQUAT": "Squats.csv", "PLANK": "Plank.csv", "DIP": "Tricep dips.csv",
    "PUSHUP": "Pushups.csv", "PULLUP": "Pullups.csv", "TWIST": "Russian twists.csv",
    "BICEP": "Barbell bicep curl.csv", "HAMMER": "Hammer curl.csv",
    "LATERAL": "Lateral raise.csv", "PRESS": "Shoulder press.csv",
    "BENCH": "Benchpress.csv", "INCLINE": "Inclined bench press.csv",
    "DECLINE": "Decline bench press.csv", "FLY": "Chest fly machine.csv",
    "DEADLIFT": "Deadlift.csv", "RDL": "Romanian deadlifts.csv",
    "HIPTHRUST": "Hip Thrust.csv", "PULLDOWN": "Lat pulldown.csv",
    "TBAR": "T bar row.csv", "LEGEXT": "Leg extension.csv",
    "LEGRAISE": "Leg raises.csv", "PUSHDOWN": "Tricep pushdowns.csv",
}

ARM = ("shoulder", "elbow", "wrist")
LEG = ("hip", "knee", "ankle")


def rom_thresholds(low, high, frac=0.30):
    """Turns a calibrated range of motion into a hysteresis pair of rep
    thresholds: cross REST_THR to be counted back at the start, cross WORK_THR
    to be counted in the worked position.

    The original ten exercises used `target +/- fixed BUFFER` instead. That works
    when the buffer happens to suit the movement's range, and silently stops
    counting reps when it does not - a 20-degree buffer is generous on a 40-degree
    chest fly and meaningless on a 150-degree hinge. Expressing the thresholds as
    a FRACTION of each movement's own measured range makes one number correct for
    all of them, and guarantees the two thresholds never cross (which would make
    a rep uncountable).
    """
    span = abs(high - low)
    return low + frac * span, high - frac * span


def _src(*calibrations):
    """Collapses several Calibration objects into one provenance label + note."""
    sources = {c.source for c in calibrations}
    if sources == {"golden"}:
        label = "golden"
    elif sources == {"fallback"}:
        label = "fallback"
    elif sources <= {"golden", "clamped"}:
        label = "clamped"
    else:
        label = "mixed"
    notes = "; ".join(c.reason for c in calibrations if c.source != "golden")
    return label, notes


def build_specs(side="auto", calib_side=None, gates=True, validate=True):
    """Builds every exercise spec.

    side / calib_side / gates exist so the migration from the original
    hand-written analyzers can be PROVEN equivalent: building with side="r",
    calib_side="r", gates=False reproduces the original right-side-only,
    ungated behaviour exactly, and the test suite asserts frame-by-frame
    equality against the frozen original engine before the improved defaults
    are switched on.
    """
    def vis(threshold):
        return threshold if gates else 0.0

    def cal(*args, **kwargs):
        """calibrate_angle with this build's side and validation policy applied."""
        kwargs.setdefault("side", calib_side)
        if not validate:
            kwargs["min_visibility"] = 0.0
            kwargs["min_range"] = 0.0
        return calibrate_angle(*args, **kwargs)

    specs = {}

    # ==================================================================
    # 1. SQUAT
    # ==================================================================
    depth = cal("Squats.csv", *LEG, "flexion", 95)
    # max(depth, 90): a squat target tighter than 90 degrees of knee bend is below
    # the depth at which the pelvis typically starts to tuck, so the app never asks
    # a user to go deeper than parallel-ish no matter what the recording showed.
    squat_target = max(float(depth), 90)
    src, note = _src(depth)
    specs["SQUAT"] = ExerciseSpec(
        id="SQUAT", name="Squats", reads=("hip", "knee", "ankle", "shoulder"),
        side=side, min_visibility=vis(0.35),
        calibration_source=src, calibration_notes=note or f"depth {squat_target:.0f} deg",
        params={
            "STAND": 160, "TARGET": squat_target,
            "BUF_MAX": squat_target + 15, "BUF_MIN": squat_target - 20,
            "BACK_PERFECT_MAX": 45, "BACK_WARNING_MAX": 60,
            "HIP_WIDTH_MIN": 0.1, "KNEE_WIDTH_RATIO": 0.7, "CAVE_BELOW": 140,
        },
        metrics={
            "leg": angle("hip", "knee", "ankle"),
            "back": smoothed("squat_back", lean("hip", "shoulder"), alpha=0.8),
            "hip_width": x_gap("l_hip", "r_hip"),
            "knee_ratio": width_ratio("l_knee", "r_knee", "l_hip", "r_hip"),
        },
        rep=RepPhase(
            rest_when=lambda M, P: M["leg"] > P["STAND"],
            work_when=lambda M, P: M["leg"] < P["BUF_MAX"],
            rest_stage="UP", work_stage="DOWN", require_prev=True,
        ),
        rules=[
            Rule(lambda M, P: M["leg"] > P["STAND"], "STAND READY", WHITE),
            Rule(lambda M, P: M["hip_width"] > P["HIP_WIDTH_MIN"]
                 and M["knee_ratio"] < P["KNEE_WIDTH_RATIO"] and M["leg"] < P["CAVE_BELOW"],
                 "KNEES CAVING IN! (PUSH OUT)", RED),
            Rule(lambda M, P: M["leg"] > P["BUF_MAX"] and M["_stage"] == "DOWN", "GO LOWER", ORANGE),
            Rule(lambda M, P: M["leg"] > P["BUF_MAX"], "STAND UP", WHITE),
            Rule(lambda M, P: M["leg"] < P["BUF_MIN"], "TOO DEEP (SPINE RISK)", RED),
            Rule(lambda M, P: M["back"] > P["BACK_WARNING_MAX"], "DANGER: FORWARD LEAN", RED),
            Rule(lambda M, P: M["back"] > P["BACK_PERFECT_MAX"], "FIX FORWARD LEAN", YELLOW),
        ],
        default=("PERFECT SQUAT!", GREEN),
        telemetry=[
            lambda M, P: f"Leg: {int(M['leg'])} (Must drop below: {int(P['BUF_MAX'])})",
            lambda M, P: f"Back: {int(M['back'])}",
        ],
    )

    # ==================================================================
    # 2. PLANK  (hold, no reps)
    # ==================================================================
    p_hip = cal("Plank.csv", "shoulder", "hip", "knee", "static", 172)
    p_knee = cal("Plank.csv", *LEG, "static", 175)
    src, note = _src(p_hip, p_knee)
    specs["PLANK"] = ExerciseSpec(
        id="PLANK", name="Planks", reads=("shoulder", "hip", "knee", "ankle"),
        side=side, min_visibility=vis(0.35),
        calibration_source=src, calibration_notes=note,
        params={"HIP_MIN": float(p_hip) - 10, "KNEE_MIN": float(p_knee) - 10},
        metrics={
            "hip": angle("shoulder", "hip", "knee"),
            "knee": angle("hip", "knee", "ankle"),
        },
        rules=[
            Rule(lambda M, P: M["hip"] < P["HIP_MIN"], "STRAIGHTEN HIPS", RED),
            Rule(lambda M, P: M["knee"] < P["KNEE_MIN"], "STRAIGHTEN KNEES", ORANGE),
        ],
        default=("PERFECT PLANK", GREEN),
        telemetry=[
            lambda M, P: f"Hip: {int(M['hip'])}",
            lambda M, P: f"Knee: {int(M['knee'])}",
        ],
    )

    # ==================================================================
    # 3. TRICEP DIPS
    # ==================================================================
    dip = cal("Tricep dips.csv", *ARM, "flexion", 90)
    src, note = _src(dip)
    specs["DIP"] = ExerciseSpec(
        id="DIP", name="Tricep Dips", reads=ARM, side=side, min_visibility=vis(0.35),
        calibration_source=src, calibration_notes=note,
        params={"UP_STATE": 150, "TARGET": float(dip), "BUFFER": 15},
        metrics={"elbow": angle("shoulder", "elbow", "wrist")},
        rep=RepPhase(
            rest_when=lambda M, P: M["elbow"] > P["UP_STATE"],
            work_when=lambda M, P: M["elbow"] < P["TARGET"] + P["BUFFER"],
            rest_stage="UP", work_stage="DOWN", require_prev=True,
        ),
        rules=[
            Rule(lambda M, P: M["elbow"] > P["UP_STATE"], "READY", WHITE),
            Rule(lambda M, P: M["elbow"] > P["TARGET"] + P["BUFFER"], "GO LOWER", RED),
            Rule(lambda M, P: M["elbow"] >= P["TARGET"] - 10, "PERFECT DEPTH", GREEN),
        ],
        default=("TOO DEEP (SHOULDER RISK)", ORANGE),
        telemetry=[lambda M, P: f"Elbow: {int(M['elbow'])}"],
    )

    # ==================================================================
    # 4. PUSHUPS
    # ==================================================================
    pu = cal("Pushups.csv", *ARM, "flexion", 90)
    src, note = _src(pu)
    specs["PUSHUP"] = ExerciseSpec(
        id="PUSHUP", name="Pushups", reads=("shoulder", "elbow", "wrist", "hip", "knee"),
        side=side, min_visibility=vis(0.35),
        calibration_source=src, calibration_notes=note,
        params={"UP_STATE": 150, "TARGET": float(pu), "BUFFER": 25,
                "HIP_MIN": 150, "FLARE_MAX": 75},
        metrics={
            "elbow": angle("shoulder", "elbow", "wrist"),
            "hip": angle("shoulder", "hip", "knee"),
            "flare": angle("hip", "shoulder", "elbow"),
        },
        rep=RepPhase(
            rest_when=lambda M, P: M["elbow"] > P["UP_STATE"],
            work_when=lambda M, P: M["elbow"] < P["TARGET"] + P["BUFFER"],
            rest_stage="UP", work_stage="DOWN", require_prev=True,
        ),
        rules=[
            Rule(lambda M, P: M["hip"] < P["HIP_MIN"], "HIPS SAGGING", RED),
            Rule(lambda M, P: M["flare"] > P["FLARE_MAX"], "TUCK ELBOWS (DON'T FLARE)", RED),
            Rule(lambda M, P: M["elbow"] > P["UP_STATE"] - 10, "ARMS EXTENDED (LOWER DOWN)", WHITE),
            Rule(lambda M, P: M["elbow"] > P["TARGET"] + P["BUFFER"] and M["_stage"] == "DOWN",
                 "GO LOWER", ORANGE),
            Rule(lambda M, P: M["elbow"] > P["TARGET"] + P["BUFFER"], "PUSH BACK UP", YELLOW),
        ],
        default=("PERFECT PUSHUP DEPTH", GREEN),
        telemetry=[
            lambda M, P: f"Elbow: {int(M['elbow'])}",
            lambda M, P: f"Flare: {int(M['flare'])} (Target: <{int(P['FLARE_MAX'])})",
        ],
    )

    # ==================================================================
    # 5. PULLUPS
    # ==================================================================
    pull = cal("Pullups.csv", *ARM, "flexion", 60)
    src, note = _src(pull)
    specs["PULLUP"] = ExerciseSpec(
        id="PULLUP", name="Pullups", reads=ARM, side=side, min_visibility=vis(0.35),
        calibration_source=src, calibration_notes=note,
        params={"HANG": 150, "TARGET_TOP": float(pull), "BUFFER": 20},
        metrics={"elbow": angle("shoulder", "elbow", "wrist")},
        rep=RepPhase(
            rest_when=lambda M, P: M["elbow"] > P["HANG"],
            work_when=lambda M, P: M["elbow"] < P["TARGET_TOP"] + P["BUFFER"],
            rest_stage="DOWN", work_stage="UP", require_prev=True, initial="UP",
        ),
        rules=[
            Rule(lambda M, P: M["elbow"] > P["HANG"], "DEAD HANG", WHITE),
            Rule(lambda M, P: M["elbow"] > P["TARGET_TOP"] + P["BUFFER"], "PULL HIGHER", RED),
        ],
        default=("PERFECT REP", GREEN),
        telemetry=[lambda M, P: f"Elbow: {int(M['elbow'])}"],
    )

    # ==================================================================
    # 6. RUSSIAN TWISTS  (hold posture, no reps)
    # ==================================================================
    tw = cal("Russian twists.csv", "shoulder", "hip", "knee", "static", 80)
    src, note = _src(tw)
    specs["TWIST"] = ExerciseSpec(
        id="TWIST", name="Russian Twists", reads=("shoulder", "hip", "knee"),
        side=side, min_visibility=vis(0.35),
        calibration_source=src, calibration_notes=note,
        params={"TARGET_POSTURE": float(tw), "BUFFER": 15},
        metrics={"core": angle("shoulder", "hip", "knee")},
        rules=[
            Rule(lambda M, P: M["core"] > P["TARGET_POSTURE"] + P["BUFFER"], "LEAN BACK MORE", RED),
            Rule(lambda M, P: M["core"] < P["TARGET_POSTURE"] - P["BUFFER"],
                 "SITTING TOO FAR BACK", ORANGE),
        ],
        default=("PERFECT V-HOLD POSTURE", GREEN),
        telemetry=[lambda M, P: f"Core Angle: {int(M['core'])}"],
    )

    # ==================================================================
    # 7 & 8. BICEP / HAMMER CURLS
    # The two differ only in calibrated target and how much elbow drift is
    # tolerated (a neutral-grip hammer curl naturally sits slightly wider), so
    # they are built from one shared factory rather than duplicated.
    # ==================================================================
    def _curl(spec_id, name, csv, flare_max, peak_msg, lower_msg, require_prev):
        target = cal(csv, *ARM, "flexion", 45)
        s, n = _src(target)
        return ExerciseSpec(
            id=spec_id, name=name, reads=("shoulder", "elbow", "wrist", "hip"),
            side=side, min_visibility=vis(0.35),
            calibration_source=s, calibration_notes=n,
            params={"EXTENDED": 150, "TARGET": float(target), "BUFFER": 15,
                    "FLARE_MAX": flare_max, "LATERAL_MAX": 0.15},
            metrics={
                "elbow": angle("shoulder", "elbow", "wrist"),
                "flare": angle("hip", "shoulder", "elbow"),
                "drift": x_gap("elbow", "shoulder"),
            },
            rep=RepPhase(
                rest_when=lambda M, P: M["elbow"] > P["EXTENDED"],
                work_when=lambda M, P: M["elbow"] < P["TARGET"] + P["BUFFER"],
                rest_stage="DOWN", work_stage="UP", require_prev=require_prev, initial="UP",
            ),
            rules=[
                Rule(lambda M, P: M["flare"] > P["FLARE_MAX"] or M["drift"] > P["LATERAL_MAX"],
                     "TUCK ELBOWS IN", RED),
                Rule(lambda M, P: M["elbow"] > P["EXTENDED"] - 10, "ARMS EXTENDED", WHITE),
                Rule(lambda M, P: M["elbow"] > P["TARGET"] + P["BUFFER"] and M["_stage"] == "DOWN",
                     "CURL HIGHER", ORANGE),
                Rule(lambda M, P: M["elbow"] > P["TARGET"] + P["BUFFER"], lower_msg, YELLOW),
            ],
            default=(peak_msg, GREEN),
            telemetry=[lambda M, P: f"Elbow: {int(M['elbow'])}"],
        )

    specs["BICEP"] = _curl("BICEP", "Bicep Curls", "Barbell bicep curl.csv", 25,
                           "PERFECT PEAK!", "LOWER WEIGHT SLOWLY", require_prev=True)
    # require_prev=False preserves the original hammer-curl behaviour exactly.
    specs["HAMMER"] = _curl("HAMMER", "Hammer Curls", "Hammer curl.csv", 35,
                            "PERFECT HAMMER", "LOWER DOWN", require_prev=False)

    # ==================================================================
    # 9. LATERAL RAISES
    # ==================================================================
    lat = cal("Lateral raise.csv", "hip", "shoulder", "elbow", "extension", 90)
    # Capped at 85 degrees: above shoulder height the subacromial space narrows,
    # so the app never coaches a user past that even if the recording went higher.
    lat_target = min(float(lat) - 10, 85)
    src, note = _src(lat)
    specs["LATERAL"] = ExerciseSpec(
        id="LATERAL", name="Lateral Raises", reads=("hip", "shoulder", "elbow", "wrist"),
        side=side, min_visibility=vis(0.35),
        calibration_source=src, calibration_notes=note or f"capped at {lat_target:.0f} deg",
        params={"DOWN": 30, "TARGET_UP": lat_target, "BUFFER": 15, "ELBOW_MIN": 140},
        metrics={
            "raise": angle("hip", "shoulder", "elbow"),
            "elbow": angle("shoulder", "elbow", "wrist"),
        },
        rep=RepPhase(
            rest_when=lambda M, P: M["raise"] < P["DOWN"],
            work_when=lambda M, P: M["raise"] > P["TARGET_UP"] - P["BUFFER"],
            rest_stage="DOWN", work_stage="UP", require_prev=False, initial="UP",
        ),
        rules=[
            Rule(lambda M, P: M["elbow"] < P["ELBOW_MIN"], "STRAIGHTEN ARMS (TOO BENT)", RED),
            Rule(lambda M, P: M["raise"] > P["TARGET_UP"] + P["BUFFER"], "TOO HIGH (LOWER ARMS)", RED),
            Rule(lambda M, P: M["raise"] < P["TARGET_UP"] - P["BUFFER"] and M["_stage"] == "DOWN",
                 "RAISE ARMS HIGHER", ORANGE),
            Rule(lambda M, P: M["raise"] < P["TARGET_UP"] - P["BUFFER"], "LOWER ARMS", YELLOW),
        ],
        default=("PERFECT HEIGHT", GREEN),
        telemetry=[
            lambda M, P: f"Shoulder Raise: {int(M['raise'])} (Target: {int(P['TARGET_UP'])})",
            lambda M, P: f"Elbow Bend: {int(M['elbow'])}",
        ],
    )

    # ==================================================================
    # 10. SHOULDER PRESS
    # The most heavily validated spec in the app. See the long-form notes in
    # tests/legacy/config_legacy.py for the three elbow-depth designs that were
    # tried and rejected before settling on a phase-indexed reference in x/y
    # rather than anything built on MediaPipe's landmark.z.
    # ==================================================================
    press = cal("Shoulder press.csv", *ARM, "extension", 160)
    rise_ref = build_phase_reference(
        "Shoulder press.csv",
        phase=lambda L: (
            calculate_angle(L.p("r_shoulder"), L.p("r_elbow"), L.p("r_wrist"))
            + calculate_angle(L.p("l_shoulder"), L.p("l_elbow"), L.p("l_wrist"))
        ) / 2,
        value=lambda L: (L.y("r_shoulder") + L.y("l_shoulder")) / 2
                        - (L.y("r_elbow") + L.y("l_elbow")) / 2,
    )
    src, note = _src(press)
    specs["PRESS"] = ExerciseSpec(
        id="PRESS", name="Shoulder Press", reads=("shoulder", "elbow", "wrist", "hip"),
        side=side, min_visibility=vis(0.35),
        calibration_source=src, calibration_notes=note,
        params={
            "TARGET_EXTENSION": float(press), "BUFFER": 15, "TARGET_START": 70,
            "BACK_LEAN_MAX": 20, "ASYM_MAX": 55, "WRIST_ELBOW_MAX": -0.03,
            "ELBOW_RISE_STDEV_MAX": 3.0, "ELBOW_RISE_REFERENCE": rise_ref,
            "ELBOW_FORWARD_MARGIN": 0.5, "ELBOW_BACK_MARGIN": 0.5,
            "ELBOW_FORWARD_REFERENCE": None, "ELBOW_BACK_REFERENCE": None,
        },
        metrics={
            "r_elbow": side_angle("r", *ARM),
            "l_elbow": side_angle("l", *ARM),
            "elbow": bilateral_angle(*ARM),
            "asym": asymmetry(*ARM),
            # Mean elbow depth relative to the shoulder. Only consumed by the two
            # z-based drift checks, which ship DISABLED (their references are None)
            # after measurement showed MediaPipe's monocular z is too noisy to
            # separate this fault from normal rep-to-rep variation.
            "elbow_z": lambda L, M, S, P: ((L.z("l_elbow") - L.z("l_shoulder"))
                                           + (L.z("r_elbow") - L.z("r_shoulder"))) / 2,
            "wrist_vs_shoulder": bilateral_y_diff("wrist", "shoulder"),
            "wrist_vs_elbow": bilateral_y_diff("wrist", "elbow"),
            "elbow_rise": bilateral_y_diff("shoulder", "elbow"),
            "back": midpoint_lean("hip", "shoulder"),
            "rise_dev": binned_deviation("elbow_rise", "elbow", "ELBOW_RISE_REFERENCE"),
            "fwd_dev": lambda L, M, S, P: -binned_deviation(
                "elbow_z", "elbow", "ELBOW_FORWARD_REFERENCE")(L, M, S, P),
            "back_dev": binned_deviation("elbow_z", "elbow", "ELBOW_BACK_REFERENCE"),
        },
        rep=RepPhase(
            rest_when=lambda M, P: M["elbow"] > P["TARGET_EXTENSION"] - P["BUFFER"],
            work_when=lambda M, P: M["elbow"] <= P["TARGET_START"],
            rest_stage="UP", work_stage="DOWN", require_prev=True,
        ),
        rules=[
            Rule(lambda M, P: M["wrist_vs_shoulder"] > 0, "RAISE WEIGHTS TO SHOULDERS", WHITE),
            Rule(lambda M, P: M["back"] > P["BACK_LEAN_MAX"],
                 "KEEP TORSO UPRIGHT (DON'T LEAN)", RED),
            Rule(lambda M, P: M["wrist_vs_elbow"] > P["WRIST_ELBOW_MAX"],
                 "KEEP WRISTS ABOVE ELBOWS", RED),
            Rule(lambda M, P: M["fwd_dev"] > P["ELBOW_FORWARD_MARGIN"],
                 "ELBOWS TOO FAR FORWARD (ROTATE BACK)", RED),
            Rule(lambda M, P: M["back_dev"] > P["ELBOW_BACK_MARGIN"],
                 "ELBOWS TOO FAR BACK (BRING FORWARD SLIGHTLY)", RED),
            Rule(lambda M, P: M["rise_dev"] > P["ELBOW_RISE_STDEV_MAX"],
                 "DON'T FLARE ELBOWS (PRESS STRAIGHT UP)", RED),
            Rule(lambda M, P: M["asym"] > P["ASYM_MAX"], "UNEVEN PRESS (BALANCE ARMS)", RED),
            Rule(lambda M, P: M["elbow"] > P["TARGET_EXTENSION"] - P["BUFFER"],
                 "PERFECT PRESS!", GREEN),
            Rule(lambda M, P: M["elbow"] <= P["TARGET_START"], "GOOD DEPTH, PRESS UP!", GREEN),
            Rule(lambda M, P: M["_stage"] == "UP", "LOWER ALL THE WAY DOWN", ORANGE),
        ],
        default=("PRESS HIGHER (LOCKOUT)", YELLOW),
        telemetry=[
            lambda M, P: f"Avg Elbow: {int(M['elbow'])} (Must drop below: {int(P['TARGET_START'])})",
            lambda M, P: f"L: {int(M['l_elbow'])} | R: {int(M['r_elbow'])}",
            lambda M, P: f"Back Lean: {int(M['back'])} (Max: {int(P['BACK_LEAN_MAX'])})",
        ],
    )

    # ==================================================================
    # 11-13. BARBELL BENCH PRESS FAMILY (flat / incline / decline)
    # One factory: the three differ only in calibrated depth, lockout, and the
    # torso angle the bench itself puts you at. The injury-relevant fault is the
    # same for all three - elbows flaring wide, which drives the humeral head
    # into the acromion under load.
    # ==================================================================
    def _bench(spec_id, name, csv, flare_margin, torso_label):
        # A benched elbow bottoms out somewhere between roughly 45 and 110
        # degrees; a lockout is 150+. Anything outside those is the camera, not
        # the athlete.
        lock = cal(csv, *ARM, "extension", 165, min_range=80, plausible=(150, 180))
        depth = cal(csv, *ARM, "flexion", 70, min_range=80, plausible=(45, 110))
        s, n = _src(lock, depth)
        work_thr, rest_thr = rom_thresholds(float(depth), float(lock))

        # Elbow flare on a BENCH cannot use a fixed angle the way a pushup can.
        # Lying down, the hip->shoulder->elbow angle is measured against a
        # horizontal torso and is heavily foreshortened by wherever the camera
        # happens to sit; measured across the three bench recordings it sits
        # around 150 degrees at mid-rep, nowhere near the ~75 that means "flared"
        # on a standing movement. A fixed threshold flagged 54-71% of frames of
        # correct form.
        #
        # So flare is judged the same way the shoulder press judges elbow rise:
        # against a phase-indexed reference of what this movement's own reference
        # recording shows at each point in the rep, firing only on a deviation
        # several standard deviations beyond it.
        flare_ref = build_phase_reference(
            csv,
            phase=lambda L: calculate_angle(L.p("shoulder"), L.p("elbow"), L.p("wrist")),
            value=lambda L: calculate_angle(L.p("hip"), L.p("shoulder"), L.p("elbow")),
        )
        return ExerciseSpec(
            id=spec_id, name=name, reads=("shoulder", "elbow", "wrist", "hip"),
            side=side, min_visibility=vis(0.40),
            gate_message="MOVE CAMERA TO YOUR SIDE - ARMS NOT VISIBLE",
            calibration_source=s, calibration_notes=n or f"{torso_label}, depth {float(depth):.0f} deg",
            params={"LOCKOUT": float(lock), "DEPTH": float(depth),
                    "WORK_THR": work_thr, "REST_THR": rest_thr,
                    "FLARE_REFERENCE": flare_ref, "FLARE_MARGIN": flare_margin,
                    "WRIST_STACK_MAX": 0.09, "ASYM_MAX": 45},
            metrics={
                "elbow": angle("shoulder", "elbow", "wrist"),
                "flare": angle("hip", "shoulder", "elbow"),
                "flare_dev": binned_deviation("flare", "elbow", "FLARE_REFERENCE"),
                # Wrist should stay stacked vertically over the elbow; a wrist
                # drifting horizontally away from it means a bent-back wrist
                # taking load through the joint instead of the forearm.
                "wrist_stack": x_gap("wrist", "elbow"),
                "asym": asymmetry(*ARM),
                "both_arms": visibility("r_elbow", "l_elbow", "r_wrist", "l_wrist"),
            },
            rep=RepPhase(
                rest_when=lambda M, P: M["elbow"] > P["REST_THR"],
                work_when=lambda M, P: M["elbow"] < P["WORK_THR"],
                rest_stage="UP", work_stage="DOWN", require_prev=True,
            ),
            rules=[
                Rule(lambda M, P: M["flare_dev"] > P["FLARE_MARGIN"],
                     "TUCK ELBOWS (SHOULDER RISK)", RED),
                Rule(lambda M, P: M["wrist_stack"] > P["WRIST_STACK_MAX"],
                     "STACK WRISTS OVER ELBOWS", ORANGE),
                # Only judged when the camera can actually see both arms - on a
                # pure side view the far arm is interpolated, and comparing a
                # real arm against an invented one flags every single rep.
                Rule(lambda M, P: M["both_arms"] > 0.6 and M["asym"] > P["ASYM_MAX"],
                     "UNEVEN PRESS (BALANCE ARMS)", RED),
                Rule(lambda M, P: M["elbow"] > P["LOCKOUT"] - 10, "ARMS LOCKED (LOWER SLOWLY)", WHITE),
                Rule(lambda M, P: M["elbow"] > P["WORK_THR"] and M["_stage"] == "DOWN",
                     "LOWER TO CHEST", ORANGE),
                Rule(lambda M, P: M["elbow"] > P["WORK_THR"], "PRESS UP", YELLOW),
            ],
            default=("PERFECT DEPTH", GREEN),
            telemetry=[
                lambda M, P: f"Elbow: {int(M['elbow'])} (Depth target: {int(P['DEPTH'])})",
                lambda M, P: f"Elbow path: {M['flare_dev']:+.1f} sd (Max: {P['FLARE_MARGIN']:.1f})",
            ],
        )

    specs["BENCH"] = _bench("BENCH", "Bench Press", "Benchpress.csv", 3.0, "flat bench")
    # Incline shifts load onto the front delt, where a flared elbow is even less
    # well tolerated, so the deviation allowance tightens as the bench gets more upright.
    specs["INCLINE"] = _bench("INCLINE", "Incline Bench Press", "Inclined bench press.csv", 2.5, "incline")
    specs["DECLINE"] = _bench("DECLINE", "Decline Bench Press", "Decline bench press.csv", 3.0, "decline")

    # ==================================================================
    # 14. CHEST FLY MACHINE
    # A fly is an ARC, not a press: the elbow angle should stay roughly fixed
    # while the shoulder opens and closes. Both failure modes are measurable -
    # opening too far (anterior capsule stretched under load) and letting the
    # elbow bend and straighten (the movement has silently become a press).
    # ==================================================================
    fly_open = cal("Chest fly machine.csv", "hip", "shoulder", "elbow", "extension", 80, min_range=50,
                   plausible=(55, 100))
    fly_close = cal("Chest fly machine.csv", "hip", "shoulder", "elbow", "flexion", 15, min_range=50,
                    plausible=(0, 45))
    src, note = _src(fly_open, fly_close)
    specs["FLY"] = ExerciseSpec(
        id="FLY", name="Chest Fly Machine", reads=("shoulder", "elbow", "wrist", "hip"),
        side=side, min_visibility=vis(0.40),
        calibration_source=src, calibration_notes=note or f"open {float(fly_open):.0f} deg",
        params={"OPEN": float(fly_open), "CLOSE": float(fly_close), "BUFFER": 15,
                "OVER_STRETCH": min(float(fly_open) + 15, 95), "ELBOW_MIN": 120, "ELBOW_MAX": 178},
        metrics={
            "open": angle("hip", "shoulder", "elbow"),
            "elbow": angle("shoulder", "elbow", "wrist"),
        },
        rep=RepPhase(
            rest_when=lambda M, P: M["open"] > P["OPEN"] - P["BUFFER"],
            work_when=lambda M, P: M["open"] < P["CLOSE"] + P["BUFFER"],
            rest_stage="OPEN", work_stage="CLOSED", require_prev=True, initial="OPEN",
        ),
        rules=[
            Rule(lambda M, P: M["open"] > P["OVER_STRETCH"],
                 "TOO WIDE (SHOULDER CAPSULE STRAIN)", RED),
            Rule(lambda M, P: M["elbow"] < P["ELBOW_MIN"], "DON'T BEND ARMS (HOLD THE ARC)", ORANGE),
            Rule(lambda M, P: M["open"] > P["CLOSE"] + P["BUFFER"] and M["_stage"] == "CLOSED",
                 "OPEN SLOWLY, CONTROL THE STRETCH", YELLOW),
            Rule(lambda M, P: M["open"] > P["CLOSE"] + P["BUFFER"], "SQUEEZE CHEST TOGETHER", ORANGE),
        ],
        default=("PERFECT SQUEEZE", GREEN),
        telemetry=[
            lambda M, P: f"Arm Open: {int(M['open'])} (Max safe: {int(P['OVER_STRETCH'])})",
            lambda M, P: f"Elbow Bend: {int(M['elbow'])} (hold ~{int(P['ELBOW_MIN'])}+)",
        ],
    )

    # ==================================================================
    # 15. DEADLIFT
    # Its golden recording is unusable (hip angle moves 24 degrees across the
    # whole clip, elbows read 176-180 throughout - filmed front-on, where a hip
    # hinge is close to invisible in 2D), so every threshold here is a
    # documented fallback rather than a derived one, and the app labels it so.
    # The checks are deliberately limited to faults with an unambiguous 2D
    # signature from a side view; nothing here tries to infer spinal rounding,
    # which a single monocular camera genuinely cannot see.
    # ==================================================================
    dl_bottom = cal("Deadlift.csv", "shoulder", "hip", "knee", "flexion", 95, min_range=60)
    dl_top = cal("Deadlift.csv", "shoulder", "hip", "knee", "extension", 172, min_range=60)
    src, note = _src(dl_bottom, dl_top)
    specs["DEADLIFT"] = ExerciseSpec(
        id="DEADLIFT", name="Deadlift", reads=("shoulder", "hip", "knee", "ankle"),
        side=side, min_visibility=vis(0.45),
        gate_message="STAND SIDE-ON TO THE CAMERA - HIPS AND KNEES NOT VISIBLE",
        calibration_source=src,
        calibration_notes=note or "documented ROM fallback",
        params={"HIP_BOTTOM": float(dl_bottom), "HIP_TOP": float(dl_top), "BUFFER": 20,
                # Below this the hips have shot up ahead of the bar, leaving the
                # back to do the lifting - the classic stiff-legged failure.
                "STIFF_KNEE_MIN": 155, "STIFF_HIP_MAX": 110,
                "LEAN_BACK_MAX": 20},
        metrics={
            "hip": angle("shoulder", "hip", "knee"),
            "knee": angle("hip", "knee", "ankle"),
            "torso": smoothed("dl_torso", lean("hip", "shoulder"), alpha=0.8),
            "shoulder_below_hip": y_diff("shoulder", "hip"),
        },
        rep=RepPhase(
            rest_when=lambda M, P: M["hip"] > P["HIP_TOP"] - P["BUFFER"],
            work_when=lambda M, P: M["hip"] < P["HIP_BOTTOM"] + P["BUFFER"],
            rest_stage="UP", work_stage="DOWN", require_prev=True,
        ),
        rules=[
            Rule(lambda M, P: M["knee"] > P["STIFF_KNEE_MIN"] and M["hip"] < P["STIFF_HIP_MAX"],
                 "HIPS TOO HIGH (BACK IS DOING THE LIFT)", RED),
            # At the top the torso should be vertical, not leaning back past it -
            # a "lean back to prove lockout" habit that hyperextends the lumbar spine.
            Rule(lambda M, P: M["hip"] > P["HIP_TOP"] - 8 and M["torso"] > P["LEAN_BACK_MAX"],
                 "STAND TALL - DON'T LEAN AT LOCKOUT", RED),
            Rule(lambda M, P: M["hip"] > P["HIP_TOP"] - P["BUFFER"], "LOCKED OUT - RESET", WHITE),
            Rule(lambda M, P: M["hip"] > P["HIP_BOTTOM"] + P["BUFFER"] and M["_stage"] == "DOWN",
                 "HINGE LOWER TO THE BAR", ORANGE),
            Rule(lambda M, P: M["hip"] > P["HIP_BOTTOM"] + P["BUFFER"], "DRIVE HIPS THROUGH", YELLOW),
        ],
        default=("GOOD HINGE POSITION", GREEN),
        telemetry=[
            lambda M, P: f"Hip: {int(M['hip'])} | Knee: {int(M['knee'])}",
            lambda M, P: f"Torso lean: {int(M['torso'])}",
        ],
    )

    # ==================================================================
    # 16. ROMANIAN DEADLIFT
    # Best-behaved of the twelve new recordings: hip sweeps 102 degrees while the
    # knees stay pinned between 159 and 176 - exactly the signature that
    # separates a hinge from a squat, and what both fault checks below key on.
    # ==================================================================
    rdl_bottom = cal("Romanian deadlifts.csv", "shoulder", "hip", "knee", "flexion", 75, min_range=60,
                     plausible=(55, 110))
    rdl_top = cal("Romanian deadlifts.csv", "shoulder", "hip", "knee", "extension", 172, min_range=60,
                  plausible=(160, 180))
    src, note = _src(rdl_bottom, rdl_top)
    specs["RDL"] = ExerciseSpec(
        id="RDL", name="Romanian Deadlift", reads=("shoulder", "hip", "knee", "ankle"),
        side=side, min_visibility=vis(0.45),
        calibration_source=src, calibration_notes=note or f"hinge to {float(rdl_bottom):.0f} deg",
        params={"HIP_BOTTOM": float(rdl_bottom), "HIP_TOP": float(rdl_top),
                "WORK_THR": rom_thresholds(float(rdl_bottom), float(rdl_top))[0],
                "REST_THR": rom_thresholds(float(rdl_bottom), float(rdl_top))[1],
                "KNEE_MIN": 145, "LEAN_BACK_MAX": 20,
                # Past the hinge the pelvis tucks and the lumbar spine flexes
                # under load; stop the athlete a little short of the depth the
                # reference lift reached rather than at it.
                "HIP_FLOOR": max(float(rdl_bottom) - 12, 55)},
        metrics={
            "hip": angle("shoulder", "hip", "knee"),
            "knee": angle("hip", "knee", "ankle"),
            "torso": smoothed("rdl_torso", lean("hip", "shoulder"), alpha=0.8),
        },
        rep=RepPhase(
            rest_when=lambda M, P: M["hip"] > P["REST_THR"],
            work_when=lambda M, P: M["hip"] < P["WORK_THR"],
            rest_stage="UP", work_stage="DOWN", require_prev=True,
        ),
        rules=[
            Rule(lambda M, P: M["hip"] < P["HIP_FLOOR"], "TOO LOW (LOWER BACK ROUNDING)", RED),
            Rule(lambda M, P: M["knee"] < P["KNEE_MIN"], "KNEES BENDING - HINGE, DON'T SQUAT", ORANGE),
            # Only judged at a genuine lockout (hip within a few degrees of its
            # top), and phrased direction-neutrally on purpose: segment_lean
            # measures deviation from vertical without a sign, so it cannot tell
            # leaning back from leaning forward. Keying it to REST_THR instead
            # fired on 10% of a correct recording - frames mid-ascent where the
            # athlete was still legitimately hinged FORWARD were reported as
            # leaning BACK. At true lockout the torso should be vertical either
            # way, so the check is correct there and only there.
            Rule(lambda M, P: M["hip"] > P["HIP_TOP"] - 8 and M["torso"] > P["LEAN_BACK_MAX"],
                 "STAND TALL - DON'T LEAN AT LOCKOUT", RED),
            Rule(lambda M, P: M["hip"] > P["REST_THR"], "STANDING TALL - RESET", WHITE),
            Rule(lambda M, P: M["hip"] > P["WORK_THR"] and M["_stage"] == "DOWN",
                 "PUSH HIPS BACK FURTHER", ORANGE),
            Rule(lambda M, P: M["hip"] > P["WORK_THR"], "SQUEEZE GLUTES, STAND UP", YELLOW),
        ],
        default=("PERFECT HINGE", GREEN),
        telemetry=[
            lambda M, P: f"Hip: {int(M['hip'])} (Target: {int(P['HIP_BOTTOM'])})",
            lambda M, P: f"Knee: {int(M['knee'])} (Keep above {int(P['KNEE_MIN'])})",
        ],
    )

    # ==================================================================
    # 17. HIP THRUST
    # ==================================================================
    ht_top = cal("Hip Thrust.csv", "shoulder", "hip", "knee", "extension", 175, min_range=60,
                 plausible=(150, 180))
    ht_bottom = cal("Hip Thrust.csv", "shoulder", "hip", "knee", "flexion", 70, min_range=60,
                    plausible=(30, 110))
    src, note = _src(ht_top, ht_bottom)
    specs["HIPTHRUST"] = ExerciseSpec(
        id="HIPTHRUST", name="Hip Thrust", reads=("shoulder", "hip", "knee", "ankle"),
        side=side, min_visibility=vis(0.40),
        calibration_source=src, calibration_notes=note or f"lockout {float(ht_top):.0f} deg",
        params={"HIP_TOP": min(float(ht_top), 178), "HIP_BOTTOM": float(ht_bottom),
                "WORK_THR": rom_thresholds(float(ht_bottom), min(float(ht_top), 178))[1],
                "REST_THR": rom_thresholds(float(ht_bottom), min(float(ht_top), 178))[0],
                # A locked-out hip thrust puts the shin vertical, i.e. roughly a
                # right angle at the knee. Far off that and the feet are placed
                # wrong, which turns the lift into a quad or hamstring movement.
                "KNEE_TOP_TARGET": 90, "KNEE_TOP_TOLERANCE": 35},
        metrics={
            "hip": angle("shoulder", "hip", "knee"),
            "knee": angle("hip", "knee", "ankle"),
        },
        rep=RepPhase(
            rest_when=lambda M, P: M["hip"] < P["REST_THR"],
            work_when=lambda M, P: M["hip"] > P["WORK_THR"],
            rest_stage="DOWN", work_stage="UP", require_prev=True, initial="DOWN",
        ),
        # NOTE - deliberately NOT checked: hip hyperextension at lockout ("ribs
        # down"). The shoulder-hip-knee angle saturates at 180 degrees, so a
        # neutral lockout and an over-arched one are the SAME number to this
        # measurement; the difference lives in pelvic tilt, which a single
        # monocular camera cannot see. Shipping it would mean flagging correct
        # lockouts at random, so it is left out rather than faked.
        rules=[
            Rule(lambda M, P: M["hip"] > P["WORK_THR"]
                 and abs(M["knee"] - P["KNEE_TOP_TARGET"]) > P["KNEE_TOP_TOLERANCE"],
                 "MOVE YOUR FEET (SHINS SHOULD BE VERTICAL)", ORANGE),
            Rule(lambda M, P: M["hip"] > P["WORK_THR"], "FULL LOCKOUT - SQUEEZE", GREEN),
            Rule(lambda M, P: M["_stage"] == "UP", "LOWER UNDER CONTROL", YELLOW),
        ],
        default=("DRIVE HIPS HIGHER", ORANGE),
        telemetry=[
            lambda M, P: f"Hip: {int(M['hip'])} (Lockout: {int(P['HIP_TOP'])})",
            lambda M, P: f"Knee: {int(M['knee'])} (Target ~{int(P['KNEE_TOP_TARGET'])} at top)",
        ],
    )

    # ==================================================================
    # 18. LAT PULLDOWN
    # ==================================================================
    pd_pull = cal("Lat pulldown.csv", *ARM, "flexion", 60, min_range=70, plausible=(30, 110))
    pd_start = cal("Lat pulldown.csv", *ARM, "extension", 165, min_range=70, plausible=(150, 180))
    src, note = _src(pd_pull, pd_start)
    specs["PULLDOWN"] = ExerciseSpec(
        id="PULLDOWN", name="Lat Pulldown", reads=("shoulder", "elbow", "wrist", "hip"),
        side=side, min_visibility=vis(0.40),
        calibration_source=src, calibration_notes=note or f"pull to {float(pd_pull):.0f} deg",
        params={"PULL": float(pd_pull), "START": float(pd_start), "LEAN_MAX": 32,
                "WORK_THR": rom_thresholds(float(pd_pull), float(pd_start))[0],
                "REST_THR": rom_thresholds(float(pd_pull), float(pd_start))[1]},
        metrics={
            "elbow": angle("shoulder", "elbow", "wrist"),
            # Torso should stay near-upright. Leaning back progressively turns a
            # lat pulldown into a seated row driven by the lower back.
            "torso": smoothed("pd_torso", lean("hip", "shoulder"), alpha=0.8),
        },
        rep=RepPhase(
            rest_when=lambda M, P: M["elbow"] > P["REST_THR"],
            work_when=lambda M, P: M["elbow"] < P["WORK_THR"],
            rest_stage="UP", work_stage="DOWN", require_prev=True,
        ),
        rules=[
            Rule(lambda M, P: M["torso"] > P["LEAN_MAX"],
                 "STOP LEANING BACK (LOWER BACK STRAIN)", RED),
            Rule(lambda M, P: M["elbow"] > P["START"] - 10, "ARMS EXTENDED - BEGIN PULL", WHITE),
            Rule(lambda M, P: M["elbow"] > P["WORK_THR"] and M["_stage"] == "DOWN",
                 "PULL TO YOUR CHEST", ORANGE),
            Rule(lambda M, P: M["elbow"] > P["WORK_THR"], "CONTROL THE RETURN", YELLOW),
        ],
        default=("PERFECT PULL", GREEN),
        telemetry=[
            lambda M, P: f"Elbow: {int(M['elbow'])} (Pull to: {int(P['PULL'])})",
            lambda M, P: f"Torso lean: {int(M['torso'])} (Max: {int(P['LEAN_MAX'])})",
        ],
    )

    # ==================================================================
    # 19. T-BAR ROW
    # Second unusable recording: the elbow sweeps only 38 degrees across the
    # whole clip and the torso only 4, so no pull and no hinge are actually
    # present to derive from. Thresholds are documented fallbacks.
    #
    # The signature fault of a row is not an angle at all - it is the torso
    # RISING through the pull to cheat the weight up with the lower back. That
    # is a drift, not a position, so it is measured against a decaying running
    # baseline of the most-hinged torso angle seen this session.
    # ==================================================================
    tb_pull = cal("T bar row.csv", *ARM, "flexion", 75, min_range=70, plausible=(50, 110))
    src, note = _src(tb_pull)
    specs["TBAR"] = ExerciseSpec(
        id="TBAR", name="T-Bar Row", reads=("shoulder", "elbow", "wrist", "hip", "knee"),
        side=side, min_visibility=vis(0.45),
        gate_message="STAND SIDE-ON TO THE CAMERA - TORSO AND ARMS NOT VISIBLE",
        calibration_source=src, calibration_notes=note or "documented ROM fallback",
        params={"PULL": float(tb_pull), "START": 165, "BUFFER": 20,
                # A T-bar row is performed hinged over; upright means the hinge
                # has been abandoned entirely.
                "HINGE_MIN": 25, "TORSO_RISE_MAX": 15},
        metrics={
            "elbow": angle("shoulder", "elbow", "wrist"),
            "torso": smoothed("tb_torso", lean("hip", "shoulder"), alpha=0.7),
            "torso_baseline": running_extreme("tb_base", "torso", kind="max", decay=0.995),
            "torso_rise": gap("torso", "torso_baseline"),
        },
        rep=RepPhase(
            rest_when=lambda M, P: M["elbow"] > P["START"] - P["BUFFER"],
            work_when=lambda M, P: M["elbow"] < P["PULL"] + P["BUFFER"],
            rest_stage="UP", work_stage="DOWN", require_prev=True,
        ),
        rules=[
            Rule(lambda M, P: M["torso_rise"] > P["TORSO_RISE_MAX"],
                 "TORSO RISING - HOLD YOUR HINGE", RED),
            Rule(lambda M, P: M["torso"] < P["HINGE_MIN"], "HINGE FORWARD MORE", ORANGE),
            Rule(lambda M, P: M["elbow"] > P["START"] - 10, "ARMS EXTENDED - BEGIN ROW", WHITE),
            Rule(lambda M, P: M["elbow"] > P["PULL"] + P["BUFFER"] and M["_stage"] == "DOWN",
                 "ROW HIGHER, ELBOWS BACK", ORANGE),
            Rule(lambda M, P: M["elbow"] > P["PULL"] + P["BUFFER"], "LOWER UNDER CONTROL", YELLOW),
        ],
        default=("PERFECT ROW", GREEN),
        telemetry=[
            lambda M, P: f"Elbow: {int(M['elbow'])} (Row to: {int(P['PULL'])})",
            lambda M, P: f"Hinge: {int(M['torso'])} (Risen {int(M['torso_rise'])} of {int(P['TORSO_RISE_MAX'])})",
        ],
    )

    # ==================================================================
    # 20. LEG EXTENSION
    # ==================================================================
    le_top = cal("Leg extension.csv", *LEG, "extension", 160, min_range=60, plausible=(135, 178))
    le_bottom = cal("Leg extension.csv", *LEG, "flexion", 60, min_range=60, plausible=(30, 100))
    src, note = _src(le_top, le_bottom)
    specs["LEGEXT"] = ExerciseSpec(
        id="LEGEXT", name="Leg Extension", reads=("hip", "knee", "ankle", "shoulder"),
        side=side, min_visibility=vis(0.40),
        calibration_source=src, calibration_notes=note or f"extend to {float(le_top):.0f} deg",
        params={"TOP": float(le_top), "BOTTOM": float(le_bottom),
                "REST_THR": rom_thresholds(float(le_bottom), float(le_top))[0],
                "WORK_THR": rom_thresholds(float(le_bottom), float(le_top))[1],
                # Snapping into full lockout drives patellofemoral compression at
                # the very end of range; stop short of it rather than at it.
                "LOCKOUT_MAX": max(float(le_top) + 8, 172),
                "SEAT_DRIFT_MAX": 12},
        metrics={
            "knee": angle("hip", "knee", "ankle"),
            # Hips peeling off the seat to swing the weight up. The obvious
            # measure - the shoulder-hip-knee angle - is WRONG here and was
            # measured to be: extending the knee moves the knee landmark, so that
            # angle sweeps 90 degrees during a correct rep purely from the
            # exercise itself, and a drift check on it fired on almost every
            # frame. Torso lean does not move with the knee (8-15 degrees across
            # the whole reference recording), so the drift is measured there.
            "torso": smoothed("le_torso", lean("hip", "shoulder"), alpha=0.8),
            "torso_baseline": running_extreme("le_base", "torso", kind="min", decay=0.995),
            "seat_drift": lambda L, M, S, P: M["torso"] - M["torso_baseline"],
        },
        rep=RepPhase(
            rest_when=lambda M, P: M["knee"] < P["REST_THR"],
            work_when=lambda M, P: M["knee"] > P["WORK_THR"],
            rest_stage="DOWN", work_stage="UP", require_prev=True, initial="DOWN",
        ),
        rules=[
            Rule(lambda M, P: M["knee"] > P["LOCKOUT_MAX"], "DON'T SNAP INTO LOCKOUT", RED),
            Rule(lambda M, P: M["seat_drift"] > P["SEAT_DRIFT_MAX"],
                 "HIPS LIFTING OFF THE SEAT", ORANGE),
            Rule(lambda M, P: M["knee"] > P["WORK_THR"], "FULL EXTENSION - SQUEEZE", GREEN),
            Rule(lambda M, P: M["_stage"] == "UP", "LOWER SLOWLY", YELLOW),
        ],
        default=("EXTEND HIGHER", ORANGE),
        telemetry=[
            lambda M, P: f"Knee: {int(M['knee'])} (Target: {int(P['TOP'])})",
            lambda M, P: f"Seat drift: {int(M['seat_drift'])} (Max: {int(P['SEAT_DRIFT_MAX'])})",
        ],
    )

    # ==================================================================
    # 21. LEG RAISES
    # ==================================================================
    lr_top = cal("Leg raises.csv", "shoulder", "hip", "knee", "flexion", 60, min_range=60,
                    plausible=(35, 95))
    lr_bottom = cal("Leg raises.csv", "shoulder", "hip", "knee", "extension", 172, min_range=60,
                       plausible=(155, 180))
    src, note = _src(lr_top, lr_bottom)
    specs["LEGRAISE"] = ExerciseSpec(
        id="LEGRAISE", name="Leg Raises", reads=("shoulder", "hip", "knee", "ankle"),
        side=side, min_visibility=vis(0.40),
        calibration_source=src, calibration_notes=note or f"raise to {float(lr_top):.0f} deg",
        params={"TOP": float(lr_top), "BOTTOM": float(lr_bottom),
                "WORK_THR": rom_thresholds(float(lr_top), float(lr_bottom))[0],
                "REST_THR": rom_thresholds(float(lr_top), float(lr_bottom))[1],
                "KNEE_MIN": 150,
                # Letting the legs settle fully flat lets the pelvis tip forward
                # and the lumbar spine arch off the floor under the legs' weight.
                "LUMBAR_RISK": min(float(lr_bottom) - 4, 174)},
        metrics={
            "hip": angle("shoulder", "hip", "knee"),
            "knee": angle("hip", "knee", "ankle"),
        },
        rep=RepPhase(
            rest_when=lambda M, P: M["hip"] > P["REST_THR"],
            work_when=lambda M, P: M["hip"] < P["WORK_THR"],
            rest_stage="DOWN", work_stage="UP", require_prev=True, initial="DOWN",
        ),
        # "Legs too low" is COACHING here, not a logged injury fault. Letting the
        # legs approach flat is where the pelvis can tip and the lumbar spine
        # arch off the floor - but whether it actually does depends on whether
        # the athlete is bracing, which the hip angle cannot distinguish. Rather
        # than log an injury the app cannot actually see, it cues the brace.
        rules=[
            Rule(lambda M, P: M["hip"] > P["LUMBAR_RISK"] and M["knee"] > P["KNEE_MIN"],
                 "KEEP LOWER BACK PRESSED DOWN", ORANGE),
            Rule(lambda M, P: M["knee"] < P["KNEE_MIN"], "STRAIGHTEN YOUR LEGS", ORANGE),
            Rule(lambda M, P: M["hip"] < P["WORK_THR"], "FULL RAISE - HOLD", GREEN),
            Rule(lambda M, P: M["_stage"] == "UP", "LOWER SLOWLY, KEEP BACK FLAT", YELLOW),
        ],
        default=("RAISE LEGS HIGHER", ORANGE),
        telemetry=[
            lambda M, P: f"Hip: {int(M['hip'])} (Raise to: {int(P['TOP'])})",
            lambda M, P: f"Knee: {int(M['knee'])} (Keep above {int(P['KNEE_MIN'])})",
        ],
    )

    # ==================================================================
    # 22. TRICEP PUSHDOWN
    # ==================================================================
    tp_ext = cal("Tricep pushdowns.csv", *ARM, "extension", 168, min_range=60, plausible=(150, 180))
    tp_flex = cal("Tricep pushdowns.csv", *ARM, "flexion", 80, min_range=60, plausible=(55, 115))
    src, note = _src(tp_ext, tp_flex)
    specs["PUSHDOWN"] = ExerciseSpec(
        id="PUSHDOWN", name="Tricep Pushdown", reads=("shoulder", "elbow", "wrist", "hip"),
        side=side, min_visibility=vis(0.40),
        calibration_source=src, calibration_notes=note or f"extend to {float(tp_ext):.0f} deg",
        params={"EXT": float(tp_ext), "FLEX": float(tp_flex), "BUFFER": 18,
                # The elbow is the pivot and must not travel. Drifting forward or
                # out recruits the shoulder and front delt instead of the tricep.
                "FLARE_MAX": 30, "LEAN_MAX": 25},
        metrics={
            "elbow": angle("shoulder", "elbow", "wrist"),
            "flare": angle("hip", "shoulder", "elbow"),
            "torso": smoothed("tp_torso", lean("hip", "shoulder"), alpha=0.8),
        },
        rep=RepPhase(
            rest_when=lambda M, P: M["elbow"] < P["FLEX"] + P["BUFFER"],
            work_when=lambda M, P: M["elbow"] > P["EXT"] - P["BUFFER"],
            rest_stage="UP", work_stage="DOWN", require_prev=True,
        ),
        rules=[
            Rule(lambda M, P: M["torso"] > P["LEAN_MAX"],
                 "STOP LEANING ON THE BAR (USE YOUR TRICEPS)", ORANGE),
            Rule(lambda M, P: M["flare"] > P["FLARE_MAX"], "PIN ELBOWS TO YOUR SIDES", ORANGE),
            Rule(lambda M, P: M["elbow"] > P["EXT"] - P["BUFFER"], "FULL EXTENSION - SQUEEZE", GREEN),
            Rule(lambda M, P: M["_stage"] == "DOWN", "RETURN SLOWLY", YELLOW),
        ],
        default=("PUSH ALL THE WAY DOWN", ORANGE),
        telemetry=[
            lambda M, P: f"Elbow: {int(M['elbow'])} (Extend to: {int(P['EXT'])})",
            lambda M, P: f"Elbow drift: {int(M['flare'])} (Max: {int(P['FLARE_MAX'])})",
        ],
    )

    # Today's scope: the ten already-shipped exercises plus the five whose
    # golden recordings calibrate cleanly. The remaining seven are drafted above
    # and pass import, but stay disabled until they have been tuned and measured
    # against their own recordings the same way - a spec that has not been
    # validated has no business giving a user injury advice.
    DRAFT = ("BENCH", "INCLINE", "DECLINE", "FLY", "DEADLIFT", "TBAR", "PUSHDOWN")
    for draft_id in DRAFT:
        specs[draft_id].enabled = False

    return specs


def enabled_specs(**kwargs):
    """The specs the app actually offers."""
    return {k: v for k, v in build_specs(**kwargs).items() if v.enabled}
