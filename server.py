import asyncio
import websockets
import json
from engine import (
    analyze_squat, analyze_plank, analyze_tricep_dip, 
    analyze_pushup, analyze_pullup, analyze_russian_twist,
    analyze_bicep_curl, analyze_hammer_curl, 
    analyze_lateral_raise, analyze_shoulder_press
)

# Mock class to mimic MediaPipe Landmark structure for engine.py
class MockLandmark:
    def __init__(self, x, y, z, visibility):
        self.x = x
        self.y = y
        self.z = z
        self.visibility = visibility

# Global state tracker per session
state_store = {
    "stage": "UP",
    "prev_back": 0
}

async def process_frame(websocket):
    global state_store
    
    async for message in websocket:
        try:
            data = json.loads(message)
            mode = data.get("mode")
            raw_landmarks = data.get("landmarks")
            
            if not raw_landmarks:
                await websocket.send(json.dumps({"error": "No landmarks"}))
                continue
                
            # Convert JSON dict array to MockLandmark array
            landmarks = [
                MockLandmark(lm.get('x', 0), lm.get('y', 0), lm.get('z', 0), lm.get('visibility', 0))
                for lm in raw_landmarks
            ]
            
            fb, clr, stage, tel = "", (255,255,255), state_store["stage"], []
            
            # Route to engine.py
            if mode == "SQUAT":
                fb, clr, state_store["stage"], state_store["prev_back"], tel = analyze_squat(landmarks, state_store["stage"], state_store["prev_back"])
            elif mode == "PLANK":
                fb, clr, tel = analyze_plank(landmarks)
            elif mode == "DIP":
                fb, clr, state_store["stage"], tel = analyze_tricep_dip(landmarks, state_store["stage"])
            elif mode == "PUSHUP":
                fb, clr, state_store["stage"], tel = analyze_pushup(landmarks, state_store["stage"])
            elif mode == "PULLUP":
                fb, clr, state_store["stage"], tel = analyze_pullup(landmarks, state_store["stage"])
            elif mode == "TWIST":
                fb, clr, tel = analyze_russian_twist(landmarks)
            elif mode == "BICEP":
                fb, clr, state_store["stage"], tel = analyze_bicep_curl(landmarks, state_store["stage"])
            elif mode == "HAMMER":
                fb, clr, state_store["stage"], tel = analyze_hammer_curl(landmarks, state_store["stage"])
            elif mode == "LATERAL":
                fb, clr, state_store["stage"], tel = analyze_lateral_raise(landmarks, state_store["stage"])
            elif mode == "PRESS":
                fb, clr, state_store["stage"], tel = analyze_shoulder_press(landmarks, state_store["stage"])
            
            # Convert BGR (OpenCV) color to Hex or RGB string for CSS
            css_color = f"rgb({clr[2]}, {clr[1]}, {clr[0]})"
                
            response = {
                "feedback": fb,
                "color": css_color,
                "telemetry": tel,
                "stage": state_store["stage"]
            }
            
            await websocket.send(json.dumps(response))
            
        except Exception as e:
            print("Error processing frame:", str(e))

async def main():
    async with websockets.serve(process_frame, "localhost", 8000):
        print("Python Fitness Engine WebSocket Server running on ws://localhost:8000")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
