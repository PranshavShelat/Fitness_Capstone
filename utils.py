"""Voice feedback for the desktop (OpenCV) app.

calculate_angle now lives in pose_math.py alongside the rest of the pose
geometry and is re-exported here so existing imports keep working. The gTTS and
playsound imports are deliberately INSIDE the playback function: server.py and
the test suite import this module's maths but have no use for audio, and a
missing audio backend should not stop the form engine from running.
"""
import os
import threading
import time

from pose_math import calculate_angle  # noqa: F401  (re-exported for compatibility)

_last_spoken_at = 0.0
SPEAK_COOLDOWN_SECONDS = 2.5

# Set once if the audio backend turns out to be unavailable, so a missing gTTS
# or playsound install fails quietly the first time instead of printing a thread
# traceback every few seconds for the whole workout.
_audio_disabled = False


def _play_audio_in_background(text):
    global _audio_disabled
    filename = None
    try:
        from gtts import gTTS
        from playsound import playsound

        os.makedirs("voice_files", exist_ok=True)
        filename = f"voice_files/voice_{int(time.time() * 1000)}.mp3"
        gTTS(text=text, lang="en").save(filename)
        playsound(filename)
    except ImportError:
        _audio_disabled = True
        print("Voice coaching is off: install gTTS and playsound to enable it.")
    except Exception:
        # A single failed clip (no network for gTTS, busy audio device) should
        # never interrupt the workout - drop it and carry on.
        pass
    finally:
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
            except OSError:
                pass


def speak(text, force=False):
    """voice_coach.VoiceCoach decides when to talk; the cooldown is only a
    safety net. force=True (urgent injury cues) bypasses it."""
    global _last_spoken_at
    if not text or _audio_disabled:
        return
    if not force and time.time() - _last_spoken_at < SPEAK_COOLDOWN_SECONDS:
        return
    _last_spoken_at = time.time()
    threading.Thread(target=_play_audio_in_background, args=(text,), daemon=True).start()
