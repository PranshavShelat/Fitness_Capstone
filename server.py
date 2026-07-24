import asyncio
import base64
import os
import time
import websockets
import json
from dotenv import load_dotenv
from websockets.datastructures import Headers
from websockets.http11 import Response

load_dotenv()

from engine import (
    analyze_squat, analyze_plank, analyze_tricep_dip,
    analyze_pushup, analyze_pullup, analyze_russian_twist,
    analyze_bicep_curl, analyze_hammer_curl,
    analyze_lateral_raise, analyze_shoulder_press
)
from db import init_db, log_fault
from injury_knowledge import MISHAP_EXPLANATIONS
from report import generate_report_pdf, REPORTS_DIR

# Mock class to mimic MediaPipe Landmark structure for engine.py
class MockLandmark:
    def __init__(self, x, y, z, visibility):
        self.x = x
        self.y = y
        self.z = z
        self.visibility = visibility

# mode -> (worked_stage, rest_stage); a rep completes on worked_stage -> rest_stage
REP_TRANSITIONS = {
    "SQUAT": ("DOWN", "UP"),
    "DIP": ("DOWN", "UP"),
    "PUSHUP": ("DOWN", "UP"),
    "PULLUP": ("UP", "DOWN"),
    "BICEP": ("UP", "DOWN"),
    "HAMMER": ("UP", "DOWN"),
    "LATERAL": ("UP", "DOWN"),
    "PRESS": ("UP", "DOWN"),
}

async def process_frame(websocket):
    # Per-connection state - each call to process_frame is a fresh connection,
    # so this is naturally isolated per client (no cross-client leakage).
    session = {"stage": "UP", "prev_back": 0, "mode": None, "last_plank_ts": None, "last_fault": None}

    async for message in websocket:
        try:
            data = json.loads(message)

            if data.get("action") == "generate_report":
                try:
                    filename, pdf_bytes = await asyncio.to_thread(
                        generate_report_pdf,
                        data.get("session_id"),
                        data.get("duration_seconds", 0),
                        data.get("rep_counts", {}),
                        data.get("plank_hold_seconds", 0),
                    )
                    await websocket.send(json.dumps({
                        "action": "report_ready",
                        "filename": filename,
                        "pdf_base64": base64.b64encode(pdf_bytes).decode("ascii"),
                    }))
                except Exception as report_error:
                    await websocket.send(json.dumps({
                        "action": "report_error",
                        "message": str(report_error),
                    }))
                continue

            mode = data.get("mode")
            session_id = data.get("session_id")
            raw_landmarks = data.get("landmarks")

            if not raw_landmarks:
                await websocket.send(json.dumps({"error": "No landmarks"}))
                continue

            # Convert JSON dict array to MockLandmark array
            landmarks = [
                MockLandmark(lm.get('x', 0), lm.get('y', 0), lm.get('z', 0), lm.get('visibility', 0))
                for lm in raw_landmarks
            ]

            # Reset stage/back-angle/plank-timer when switching exercises so
            # stale state from the previous exercise doesn't bleed into this one.
            if session["mode"] is not None and mode != session["mode"]:
                session["stage"] = "UP"
                session["prev_back"] = 0
                session["last_plank_ts"] = None
                session["last_fault"] = None
            session["mode"] = mode

            prev_stage = session["stage"]

            fb, clr, tel = "", (255, 255, 255), []

            # Route to engine.py
            if mode == "SQUAT":
                fb, clr, session["stage"], session["prev_back"], tel = analyze_squat(landmarks, session["stage"], session["prev_back"])
            elif mode == "PLANK":
                fb, clr, tel = analyze_plank(landmarks)
            elif mode == "DIP":
                fb, clr, session["stage"], tel = analyze_tricep_dip(landmarks, session["stage"])
            elif mode == "PUSHUP":
                fb, clr, session["stage"], tel = analyze_pushup(landmarks, session["stage"])
            elif mode == "PULLUP":
                fb, clr, session["stage"], tel = analyze_pullup(landmarks, session["stage"])
            elif mode == "TWIST":
                fb, clr, tel = analyze_russian_twist(landmarks)
            elif mode == "BICEP":
                fb, clr, session["stage"], tel = analyze_bicep_curl(landmarks, session["stage"])
            elif mode == "HAMMER":
                fb, clr, session["stage"], tel = analyze_hammer_curl(landmarks, session["stage"])
            elif mode == "LATERAL":
                fb, clr, session["stage"], tel = analyze_lateral_raise(landmarks, session["stage"])
            elif mode == "PRESS":
                fb, clr, session["stage"], tel = analyze_shoulder_press(landmarks, session["stage"])

            # Detect a completed rep via the worked -> rest stage transition
            rep_completed = False
            if mode in REP_TRANSITIONS:
                worked, rest = REP_TRANSITIONS[mode]
                if prev_stage == worked and session["stage"] == rest:
                    rep_completed = True

            # Track plank hold time as a wall-clock delta since the last PLANK frame
            plank_hold_delta = 0.0
            if mode == "PLANK":
                now = time.monotonic()
                if session["last_plank_ts"] is not None:
                    plank_hold_delta = min(now - session["last_plank_ts"], 2.0)
                session["last_plank_ts"] = now

            # Log a mishap on the rising edge only (don't spam a row every frame
            # a fault is sustained). Keyed by session_id (not this connection) so
            # it survives a reconnect - only reset here happens on mode switch above.
            if fb in MISHAP_EXPLANATIONS and fb != session["last_fault"]:
                if session_id:
                    await asyncio.to_thread(log_fault, session_id, mode, fb, json.dumps(raw_landmarks))
                session["last_fault"] = fb
            elif fb not in MISHAP_EXPLANATIONS:
                session["last_fault"] = None

            # Convert BGR (OpenCV) color to Hex or RGB string for CSS
            css_color = f"rgb({clr[2]}, {clr[1]}, {clr[0]})"

            response = {
                "feedback": fb,
                "color": css_color,
                "telemetry": tel,
                "stage": session["stage"],
                "mode": mode,
                "repCompleted": rep_completed,
                "plankHoldDelta": round(plank_hold_delta, 3),
            }

            await websocket.send(json.dumps(response))

        except Exception as e:
            print("Error processing frame:", str(e))

def _json_response(status_code, reason, payload):
    headers = Headers()
    headers["Content-Type"] = "application/json"
    headers["Access-Control-Allow-Origin"] = "*"
    return Response(status_code, reason, headers, json.dumps(payload).encode("utf-8"))


def handle_http_request(connection, request):
    # Lets the Dashboard (which never opens the fitness-engine WebSocket) list and
    # download saved reports via plain HTTP GETs on this same port - no second
    # server/framework needed. Anything else falls through (returns None) to the
    # normal WebSocket handshake.
    if request.path == "/reports":
        os.makedirs(REPORTS_DIR, exist_ok=True)
        entries = []
        for filename in os.listdir(REPORTS_DIR):
            if not filename.endswith(".pdf"):
                continue
            full_path = os.path.join(REPORTS_DIR, filename)
            entries.append({"filename": filename, "created_at": os.path.getmtime(full_path)})
        entries.sort(key=lambda e: e["created_at"], reverse=True)
        return _json_response(200, "OK", entries)

    if request.path.startswith("/reports/"):
        filename = os.path.basename(request.path[len("/reports/"):])
        full_path = os.path.join(REPORTS_DIR, filename)
        if not filename.endswith(".pdf") or not os.path.isfile(full_path):
            return _json_response(404, "Not Found", {"error": "Report not found"})
        with open(full_path, "rb") as f:
            pdf_bytes = f.read()
        headers = Headers()
        headers["Content-Type"] = "application/pdf"
        headers["Access-Control-Allow-Origin"] = "*"
        return Response(200, "OK", headers, pdf_bytes)

    return None


async def main():
    init_db()
    async with websockets.serve(process_frame, "localhost", 8000, process_request=handle_http_request):
        print("Python Fitness Engine WebSocket Server running on ws://localhost:8000")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
