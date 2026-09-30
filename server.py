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

from engine import EXERCISES, HOLD_MODES, REP_TRANSITIONS, analyze_frame, new_state
from db import init_db, log_fault
from injury_knowledge import MISHAP_EXPLANATIONS
from report import generate_report_pdf, REPORTS_DIR
from plan import generate_workout_plan, generate_meal_plan
from coach_agent import create_chat_session, send_chat_message
from voice_coach import VoiceCoach
from gemini_util import is_transient

VALID_GOALS = ("CUT", "MAINTAIN", "BULK")
VALID_DIETS = ("VEG_EGGS", "VEG_NO_EGGS", "NON_VEG")
VALID_SEXES = ("MALE", "FEMALE")

# Mock class to mimic MediaPipe Landmark structure for engine.py
class MockLandmark:
    def __init__(self, x, y, z, visibility):
        self.x = x
        self.y = y
        self.z = z
        self.visibility = visibility

# REP_TRANSITIONS (mode -> (worked_stage, rest_stage)) is imported from engine,
# where it is derived from the exercise specs themselves - adding an exercise
# can no longer leave its rep counting silently unwired.

# Consecutive frames the same fault must be observed before it's logged as a real
# mishap (~150-250ms at typical webcam framerates) - filters out single-frame
# pose-tracking noise so it never gets written into a report as fact.
FAULT_MIN_STREAK = 5

async def _send_report(websocket, data):
    try:
        filename, pdf_bytes = await asyncio.to_thread(
            generate_report_pdf,
            data.get("session_id"),
            data.get("duration_seconds", 0),
            data.get("rep_counts", {}),
            data.get("plank_hold_seconds", 0),
            data.get("profile"),
        )
        await websocket.send(json.dumps({
            "action": "report_ready",
            "filename": filename,
            "pdf_base64": base64.b64encode(pdf_bytes).decode("ascii"),
        }))
    except websockets.ConnectionClosed:
        # The PDF is already saved in reports/ - the Dashboard can still list it.
        print("Report generated but the browser disconnected before it could be sent.")
    except Exception as report_error:
        try:
            await websocket.send(json.dumps({"action": "report_error", "message": str(report_error)}))
        except websockets.ConnectionClosed:
            pass


async def _send_chat_reply(websocket, session, data):
    # One chat at a time per connection, so replies stay in order and the
    # shared chat session is never used by two threads at once.
    async with session["chat_lock"]:
        try:
            # One chat session per WS connection, created on the first message -
            # bound to whatever profile/session_id came in with that first message,
            # then reused (with full conversation memory) for the rest of this
            # connection's messages.
            if session["chat"] is None:
                                session["chat_client"], session["chat"], session["chat_config"] = create_chat_session(
                    data.get("profile"), data.get("session_id"),
                    data.get("workout_plan"), data.get("meal_plan"),
                    plan_updates=session["plan_updates"],
                )
            reply, session["chat"] = await asyncio.to_thread(
                send_chat_message, session["chat_client"], session["chat"],
                session["chat_config"], data.get("message", ""))
            payload = {"action": "chat_reply", "reply": reply}
            payload.update(session["plan_updates"])   # workout_plan / meal_plan, if any
            session["plan_updates"].clear()
            await websocket.send(json.dumps(payload))
        except websockets.ConnectionClosed:
            pass
        except Exception as chat_error:
            session["plan_updates"].clear()   # never attach a stale plan to a later reply
            try:
                message = str(chat_error)
                if is_transient(chat_error):
                    message = ("GymBro is busy right now because Google's servers are "
                               "overloaded. Please try again in a minute.")
                await websocket.send(json.dumps({"action": "chat_error", "message": message}))
            except websockets.ConnectionClosed:
                pass


def _spawn(session, coro):
    """Run slow work (report, Gemini chat) in the background.

    It must NOT be awaited inside the message loop: while the loop is blocked,
    the camera's ~30 frames/s pile up, the websockets library stops reading the
    socket once its queue is full, the browser's keepalive pongs go unread, and
    after 20 s the server kills the connection ("1011 keepalive ping timeout")
    - which is exactly what happened to report generation once Gemini was on.
    """
    task = asyncio.create_task(coro)
    session["tasks"].add(task)
    task.add_done_callback(session["tasks"].discard)


async def process_frame(websocket):
    # Per-connection state - each call to process_frame is a fresh connection,
    # so this is naturally isolated per client (no cross-client leakage).
    session = {
        # One analyzer state per exercise, so switching away and back does not
        # lose a half-completed rep, and no exercise can inherit another's stage.
        "states": {}, "mode": None, "last_plank_ts": None,
        "fault_candidate": None, "fault_streak": 0, "fault_logged": False,
        # Both lazily created on the first chat message - "chat_client" must be kept
        # alive here for as long as "chat" is in use (see create_chat_session).
        "chat": None, "chat_client": None,
        "chat_lock": asyncio.Lock(),
        # Plans the coach chat generated during a reply - sent to the browser with
        # that reply so the dashboard cards update (filled by coach_agent's tools).
        "plan_updates": {},
        # Strong references to background tasks so they aren't garbage-collected.
        "tasks": set(),
        # Judges each 5 s window of frames and decides the ONE thing to say -
        # the browser speaks only these cues, never the raw per-frame text.
        "coach": VoiceCoach(),
    }

    async for message in websocket:
        try:
            data = json.loads(message)

            if data.get("action") == "generate_report":
                _spawn(session, _send_report(websocket, data))
                continue

            if data.get("action") == "chat":
                _spawn(session, _send_chat_reply(websocket, session, data))
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

            # Reset the plank timer and fault debounce when switching exercises
            # so stale state from the previous exercise doesn't bleed into this
            # one. Per-exercise analyzer state lives in session["states"] and is
            # kept, so returning to an exercise resumes where it left off.
            if session["mode"] is not None and mode != session["mode"]:
                session["last_plank_ts"] = None
                session["fault_candidate"] = None
                session["fault_streak"] = 0
                session["fault_logged"] = False
                session["coach"].reset()
            session["mode"] = mode

            state = session["states"].get(mode) or new_state(mode)
            prev_stage = state.get("stage") if state else None

            fb, clr, state, tel = analyze_frame(mode, landmarks, state)
            session["states"][mode] = state

            # Detect a completed rep via the worked -> rest stage transition
            rep_completed = False
            if mode in REP_TRANSITIONS:
                worked, rest = REP_TRANSITIONS[mode]
                if prev_stage == worked and state.get("stage") == rest:
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

            voice_cue = session["coach"].observe(fb, clr, rep_completed, is_hold=mode in HOLD_MODES)

            # Convert BGR (OpenCV) color to Hex or RGB string for CSS
            css_color = f"rgb({clr[2]}, {clr[1]}, {clr[0]})"

            response = {
                "feedback": fb,
                "color": css_color,
                "telemetry": tel,
                "stage": state.get("stage") if state else None,
                "mode": mode,
                "repCompleted": rep_completed,
                "plankHoldDelta": round(plank_hold_delta, 3),
                # None on most frames; {"text", "kind", "urgent", "source"} when the
                # coach has something to say (every ~5 s, or at once for an injury).
                "voiceCue": voice_cue,
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

    if path == "/exercises":
        # The React app fetches its exercise list from here instead of keeping a
        # hardcoded copy, so the two can never disagree about which exercises
        # exist or which of them count reps.
        return _json_response(200, "OK", {
            "exercises": EXERCISES,
            "repBasedModes": sorted(REP_TRANSITIONS.keys()),
        })

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

    if path == "/plan/workout":
        query = parse_qs(parsed.query)
        try:
            height_cm = float(query.get("height", [""])[0])
            weight_kg = float(query.get("weight", [""])[0])
            age = int(query.get("age", [""])[0])
            sex = query.get("sex", [""])[0].upper()
            goal = query.get("goal", [""])[0].upper()
            if height_cm <= 0 or weight_kg <= 0 or age <= 0 or sex not in VALID_SEXES or goal not in VALID_GOALS:
                raise ValueError
        except (ValueError, IndexError):
            return _json_response(400, "Bad Request", {
                "error": "height, weight, age, sex (MALE/FEMALE) and goal (CUT/MAINTAIN/BULK) are required"
            })

        try:
            plan = await asyncio.to_thread(generate_workout_plan, height_cm, weight_kg, age, sex, goal)
            return _json_response(200, "OK", plan)
        except Exception as e:
            return _json_response(500, "Internal Server Error", {"error": str(e)})

    if path == "/plan/meal":
        query = parse_qs(parsed.query)
        try:
            height_cm = float(query.get("height", [""])[0])
            weight_kg = float(query.get("weight", [""])[0])
            age = int(query.get("age", [""])[0])
            sex = query.get("sex", [""])[0].upper()
            goal = query.get("goal", [""])[0].upper()
            diet = query.get("diet", [""])[0].upper()
            if (
                height_cm <= 0 or weight_kg <= 0 or age <= 0 or sex not in VALID_SEXES
                or goal not in VALID_GOALS or diet not in VALID_DIETS
            ):
                raise ValueError
        except (ValueError, IndexError):
            return _json_response(400, "Bad Request", {
                "error": "height, weight, age, sex (MALE/FEMALE), goal (CUT/MAINTAIN/BULK) and "
                         "diet (VEG_EGGS/VEG_NO_EGGS/NON_VEG) are required"
            })

        try:
            plan = await asyncio.to_thread(generate_meal_plan, height_cm, weight_kg, age, sex, goal, diet)
            return _json_response(200, "OK", plan)
        except Exception as e:
            return _json_response(500, "Internal Server Error", {"error": str(e)})

    return None


async def main():
    init_db()
    # Build the RAG index in the background right away, so the first plan or
    # chat request doesn't have to wait for it (see rag.warm_up).
    from rag import warm_up
    asyncio.get_running_loop().run_in_executor(None, warm_up)
    # open_timeout bounds the whole opening handshake, which includes handle_http_request -
    # the default 10s is fine for a websocket handshake but too short for /plan, which calls
    # out to Gemini (with retries and a backup model when it is busy - gemini_util.py).
    async with websockets.serve(process_frame, "localhost", 8000, process_request=handle_http_request, open_timeout=120):
        print("Python Fitness Engine WebSocket Server running on ws://localhost:8000")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
