import numpy as np
from types import SimpleNamespace
from gtts import gTTS
from playsound import playsound
import time
import os
import threading

# --- MATH HELPERS ---
def calculate_angle(a, b, c):
    a = np.array(a) 
    b = np.array(b) 
    c = np.array(c) 
    
    radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angle = np.abs(radians * 180.0 / np.pi)
    
    if angle > 180.0:
        angle = 360 - angle
        
    return angle


def get_point(landmarks, landmark_enum):
    """
    Optional helper to reduce the repeated
    `[landmarks[X.value].x, landmarks[X.value].y]` pattern seen throughout
    engine.py. Not applied retroactively to existing analyze_* functions
    (that would mean editing all 11), but any NEW analyze_<exercise>()
    function can use it going forward:

        s = get_point(landmarks, mp_pose.PoseLandmark.RIGHT_SHOULDER)

    instead of:

        s = [landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x,
             landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y]
    """
    lm = landmarks[landmark_enum.value]
    return [lm.x, lm.y]


# --- LANDMARK SMOOTHING (fixes Problem 1: jitter) ---
def smooth_landmarks(raw_landmarks, prev_smoothed, dt=None, tau=0.15,
                      min_visibility=0.5, low_conf_alpha_scale=0.25):
    """
    Exponential moving average over all 33 landmark coordinates (x, y, z),
    applied ONCE per frame before any exercise-specific angle math runs.

    Why coordinate-level smoothing instead of angle-level smoothing:
    - MediaPipe jitter is noise on the *points*, and that noise propagates
      non-linearly into every angle, flare, and distance computed from them.
      Smoothing once at the source cleans up all downstream metrics
      consistently, instead of needing a separate EMA line inside every
      analyze_* function (like Squat currently has for back_angle alone).
    - It benefits every future exercise automatically -- a new
      analyze_<exercise>() function never has to think about jitter.

    Two refinements over a plain fixed-alpha EMA:

    1. TIME-BASED ALPHA (dt-driven, not frame-count-driven):
       A fixed per-frame alpha implicitly assumes a constant frame rate.
       At low or uneven FPS (e.g. a heavy camera angle dragging you to
       ~9fps), the gap between frames varies, so a fixed alpha ends up
       under-smoothing on big gaps and over-smoothing on small ones --
       which looks exactly like erratic, haphazard point movement.
       Instead we compute alpha from elapsed wall-clock time (`dt`) and a
       fixed settling time constant `tau`:
           alpha = 1 - exp(-dt / tau)
       This keeps the *actual* smoothing strength consistent (roughly a
       tau-second settling time) regardless of how fast or slow frames
       are arriving.

    2. VISIBILITY GATING:
       A landmark's `visibility` score reflects MediaPipe's own confidence
       in that point. Occluded or hard-to-see landmarks (common with
       overhead/behind-the-head camera angles, where hips and legs are
       foreshortened or out of frame) are essentially guesses -- and
       guesses are noisier than real detections. Points below
       `min_visibility` get a much smaller alpha (weighted toward
       history, not the noisy guess), so an unreliable landmark can't
       drag the smoothed skeleton around on its own.

    Returns:
        smoothed_landmarks: a list of objects exposing .x/.y/.z/.visibility,
            so it's a drop-in replacement for results.pose_landmarks.landmark
            -- engine.py needs ZERO changes to use it.
        new_prev_smoothed: numpy array to pass back in next frame.
    """
    coords = np.array([[lm.x, lm.y, lm.z] for lm in raw_landmarks])
    visibilities = np.array([lm.visibility for lm in raw_landmarks])

    if prev_smoothed is None or prev_smoothed.shape != coords.shape:
        smoothed = coords
    else:
        if dt is not None and dt > 0:
            base_alpha = 1 - np.exp(-dt / tau)
        else:
            base_alpha = 0.4  # fallback if timing isn't available

        per_point_alpha = np.where(
            visibilities >= min_visibility,
            base_alpha,
            base_alpha * low_conf_alpha_scale
        ).reshape(-1, 1)

        smoothed = per_point_alpha * coords + (1 - per_point_alpha) * prev_smoothed

    smoothed_landmarks = [
        SimpleNamespace(x=smoothed[i, 0], y=smoothed[i, 1], z=smoothed[i, 2],
                         visibility=raw_landmarks[i].visibility)
        for i in range(len(raw_landmarks))
    ]
    return smoothed_landmarks, smoothed


# --- STAGE HYSTERESIS (fixes Problem 2: stage flicker) ---
def debounce_stage(new_stage, confirmed_stage, pending_state, required_frames=3):
    """
    Sits between analyze_*() calls across frames. A proposed stage change
    (e.g. "UP" -> "DOWN") only commits once it's been proposed for
    `required_frames` consecutive frames, so a single noisy frame can't
    flip the stage and cause feedback to flicker.

    Applies uniformly to every exercise that tracks a stage -- no per-
    exercise logic needed, and works for any future exercise's stage too.

    Args:
        new_stage: stage value analyze_*() just computed this frame.
        confirmed_stage: the stage actually in use (fed into analyze_*()).
        pending_state: dict {"candidate": str, "count": int}, persisted
            by the caller (main.py) across frames. Pass None on first call.

    Returns:
        (confirmed_stage, pending_state) -- confirmed_stage is what should
        be stored and fed into next frame's analyze_*() call.
    """
    if confirmed_stage is None:
        return new_stage, {"candidate": new_stage, "count": 0}

    if pending_state is None:
        pending_state = {"candidate": confirmed_stage, "count": 0}

    if new_stage == confirmed_stage:
        # Already stable; reset any pending candidate.
        return confirmed_stage, {"candidate": confirmed_stage, "count": 0}

    if pending_state.get("candidate") == new_stage:
        pending_state["count"] += 1
    else:
        pending_state = {"candidate": new_stage, "count": 1}

    if pending_state["count"] >= required_frames:
        return new_stage, {"candidate": new_stage, "count": 0}

    return confirmed_stage, pending_state


# --- FEEDBACK STABILIZATION (fixes Problem 3: feedback flicker) ---
DANGER_COLOR = (0, 0, 255)

def stabilize_feedback(new_fb, new_color, feedback_state, min_hold_frames=4,
                        danger_color=DANGER_COLOR):
    """
    Holds the currently-displayed feedback message/color steady unless a
    NEW message persists for `min_hold_frames` consecutive frames.

    Safety override: danger-colored feedback (your existing (0,0,255) red
    convention, used consistently across all 11 exercises for injury-risk
    warnings) always passes through immediately, uncooled. Posture
    correction and injury prevention is the whole point of this project,
    so a "KNEES CAVING IN" warning must never be delayed for the sake of
    visual smoothness -- only cosmetic/informational messages get damped.

    Args:
        feedback_state: dict persisted by the caller across frames.
            Pass None on the first call.

    Returns:
        (displayed_fb, displayed_color, feedback_state)
    """
    if feedback_state is None:
        return new_fb, new_color, {"fb": new_fb, "color": new_color,
                                    "candidate": new_fb, "count": 0}

    if new_color == danger_color:
        return new_fb, new_color, {"fb": new_fb, "color": new_color,
                                    "candidate": new_fb, "count": 0}

    if new_fb == feedback_state["fb"]:
        feedback_state["candidate"] = new_fb
        feedback_state["count"] = 0
        return feedback_state["fb"], feedback_state["color"], feedback_state

    if feedback_state.get("candidate") == new_fb:
        feedback_state["count"] += 1
    else:
        feedback_state["candidate"] = new_fb
        feedback_state["count"] = 1

    if feedback_state["count"] >= min_hold_frames:
        feedback_state["fb"] = new_fb
        feedback_state["color"] = new_color
        feedback_state["count"] = 0

    return feedback_state["fb"], feedback_state["color"], feedback_state


# --- TELEMETRY (Problem 5: better debugging info, for free, every exercise) ---
def build_common_telemetry(stage, landmarks, fps=None):
    """
    Debug stats useful regardless of which exercise is active:
    - Tracking confidence: average landmark visibility. Low values explain
      *why* an exercise's feedback looks wrong (occlusion/bad framing)
      rather than it being a logic bug.
    - Stage: what state machine currently thinks you're in.
    - FPS: cheap performance sanity check while iterating.
    Appended to each exercise's own tel list in main.py, so no
    analyze_<exercise>() function needs to build these itself.
    """
    avg_visibility = float(np.mean([lm.visibility for lm in landmarks]))
    stats = [f"Stage: {stage}", f"Tracking Confidence: {avg_visibility:.2f}"]
    if fps is not None:
        stats.append(f"FPS: {fps:.1f}")
    return stats


# --- VOICE HELPERS ---
last_time = 0

def _play_audio_in_background(text):
    os.makedirs("voice_files", exist_ok=True)
    filename = f"voice_files/voice_{int(time.time() * 1000)}.mp3" 
    try:
        tts = gTTS(text=text, lang='en')
        tts.save(filename)
        playsound(filename)
        if os.path.exists(filename):
            os.remove(filename)
    except Exception:
        pass

def speak(text):
    global last_time
    if not text:
        return

    # INCREASED COOLDOWN TO 5 SECONDS
    if time.time() - last_time >= 5:
        last_time = time.time() 
        
        audio_thread = threading.Thread(target=_play_audio_in_background, args=(text,))
        audio_thread.daemon = True 
        audio_thread.start()