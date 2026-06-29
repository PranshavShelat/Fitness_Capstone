import numpy as np
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

# --- VOICE HELPERS ---
last_time = 0

def _play_audio_in_background(text):
    filename = f"voice_{int(time.time() * 1000)}.mp3" 
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