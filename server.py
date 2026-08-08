import asyncio
import base64
import os
import time
import websockets
import json
from urllib.parse import urlsplit, parse_qs
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
from config import PRESS_ELBOW_FORWARD_REFERENCE, PRESS_ELBOW_BACK_REFERENCE
from db import init_db, log_fault
from injury_knowledge import MISHAP_EXPLANATIONS
from report import generate_report_pdf, REPORTS_DIR
from plan import generate_plan

VALID_GOALS = ("CUT", "MAINTAIN", "BULK")
VALID_DIETS = ("VEG_EGGS", "VEG_NO_EGGS", "NON_VEG")

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

# Consecutive frames the same fault must be observed before it's logged as a real
# mishap (~150-250ms at typical webcam framerates) - filters out single-frame
# pose-tracking noise so it never gets written into a report as fact.
FAULT_MIN_STREAK = 5

async def process_frame(websocket):
    # Per-connection state - each call to process_frame is a fresh connection,
    # so this is naturally isolated per client (no cross-client leakage).
    session = {
        "stage": "UP", "prev_back": 0, "mode": None, "last_plank_ts": None,
        "fault_candidate": None, "fault_streak": 0, "fault_logged": False,
    }

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
                session["fault_candidate"] = None
                session["fault_streak"] = 0
                session["fault_logged"] = False
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
                fb, clr, session["stage"], tel = analyze_shoulder_press(
                    landmarks, session["stage"], PRESS_ELBOW_FORWARD_REFERENCE, PRESS_ELBOW_BACK_REFERENCE
                )

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

            # Only log a mishap once it's been sustained for a few consecutive frames -
            # a single-frame reading can be pose-tracking noise (jitter, brief camera-angle
            # skew) rather than a real, repeated form issue, and that noise would otherwise
            # end up quoted as fact in the PDF report. Logs once per sustained streak (not
            # every frame after), keyed by session_id (not this connection) so it survives
            # a reconnect - only reset here happens on mode switch above.
            if fb in MISHAP_EXPLANATIONS:
                if fb == session["fault_candidate"]:
                    session["fault_streak"] += 1
                else:
                    session["fault_candidate"] = fb
                    session["fault_streak"] = 1
                    session["fault_logged"] = False

                if session["fault_streak"] >= FAULT_MIN_STREAK and not session["fault_logged"]:
                    if session_id:
                        await asyncio.to_thread(log_fault, session_id, mode, fb)
                    session["fault_logged"] = True
            else:
                session["fault_candidate"] = None
                session["fault_streak"] = 0
                session["fault_logged"] = False

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


async def handle_http_request(connection, request):
    # Lets the Dashboard (which never opens the fitness-engine WebSocket) list and
    # download saved reports, and generate a nutrition/workout plan, via plain HTTP
    # GETs on this same port - no second server/framework needed. Anything else
    # falls through (returns None) to the normal WebSocket handshake.
    parsed = urlsplit(request.path)
    path = parsed.path

    if path == "/reports":
        os.makedirs(REPORTS_DIR, exist_ok=True)
        entries = []
        for filename in os.listdir(REPORTS_DIR):
            if not filename.endswith(".pdf"):
                continue
            full_path = os.path.join(REPORTS_DIR, filename)
            entries.append({"filename": filename, "created_at": os.path.getmtime(full_path)})
        entries.sort(key=lambda e: e["created_at"], reverse=True)
        return _json_response(200, "OK", entries)

    if path.startswith("/reports/"):
        filename = os.path.basename(path[len("/reports/"):])
        full_path = os.path.join(REPORTS_DIR, filename)
        if not filename.endswith(".pdf") or not os.path.isfile(full_path):
            return _json_response(404, "Not Found", {"error": "Report not found"})
        with open(full_path, "rb") as f:
            pdf_bytes = f.read()
        headers = Headers()
        headers["Content-Type"] = "application/pdf"
        headers["Access-Control-Allow-Origin"] = "*"
        return Response(200, "OK", headers, pdf_bytes)

    if path == "/plan":
        query = parse_qs(parsed.query)
        try:
            height_cm = float(query.get("height", [""])[0])
            weight_kg = float(query.get("weight", [""])[0])
            goal = query.get("goal", [""])[0].upper()
            diet = query.get("diet", [""])[0].upper()
            if height_cm <= 0 or weight_kg <= 0 or goal not in VALID_GOALS or diet not in VALID_DIETS:
                raise ValueError
        except (ValueError, IndexError):
            return _json_response(400, "Bad Request", {
                "error": "height, weight, goal (CUT/MAINTAIN/BULK) and diet (VEG_EGGS/VEG_NO_EGGS/NON_VEG) are required"
            })

        try:
            plan = await asyncio.to_thread(generate_plan, height_cm, weight_kg, goal, diet)
            return _json_response(200, "OK", plan)
        except Exception as e:
            return _json_response(500, "Internal Server Error", {"error": str(e)})

    return None


async def main():
    init_db()
    # open_timeout bounds the whole opening handshake, which includes handle_http_request -
    # the default 10s is fine for a websocket handshake but too short for /plan, which calls
    # out to Gemini and can take longer than that.
    async with websockets.serve(process_frame, "localhost", 8000, process_request=handle_http_request, open_timeout=60):
        print("Python Fitness Engine WebSocket Server running on ws://localhost:8000")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
