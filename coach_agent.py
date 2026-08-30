import os
from datetime import datetime

from google import genai
from google.genai import types
from pypdf import PdfReader

from db import get_faults
from plan import bmi_category, generate_workout_plan, generate_meal_plan
from rag import retrieve
from report import REPORTS_DIR

GEMINI_MODEL = "gemini-3.6-flash"

SYSTEM_INSTRUCTION_TEMPLATE = """You are an AI fitness coach embedded in a workout-tracking app. \
Today's date is {today} ({today_weekday}). Be encouraging, direct, and concise - this is a chat, \
not an essay, so keep replies short unless the user asks for detail. Never invent specifics about \
the user's past workouts, reports, or form faults - use the tools to look them up instead of \
guessing, and say so plainly if a tool turns up nothing.

The user's saved profile: {profile_context}

The user's already-generated workout plan (this is what's currently shown on their dashboard right \
now - use it directly to answer questions like "what am I training today", don't call \
generate_new_workout_plan unless they explicitly ask for a new/regenerated one):
{workout_plan_context}

The user's already-generated meal plan (this is what's currently shown on their dashboard right now \
- use it directly to answer questions like "what should I eat today", don't call \
generate_new_meal_plan unless they explicitly ask for a new/regenerated one):
{meal_plan_context}
"""


def _diet_label(profile):
    if profile.get("diet") == "NON_VEG":
        return "Non-Vegetarian"
    return "Vegetarian (eats eggs)" if profile.get("eatsEggs") else "Vegetarian (no eggs)"


def _profile_context(profile):
    if not profile or not profile.get("heightCm") or not profile.get("weightKg"):
        return "No profile saved yet - if the question depends on it, tell the user to fill out the Profile card on the dashboard first."
    height_m = profile["heightCm"] / 100
    bmi = profile["weightKg"] / (height_m * height_m)
    category = bmi_category(bmi)
    return (
        f"Height: {profile['heightCm']}cm, Weight: {profile['weightKg']}kg, "
        f"Age: {profile.get('age')}, Sex: {(profile.get('sex') or '').title()}, "
        f"BMI: {bmi:.1f} ({category}), Goal: {(profile.get('goal') or '').title()}, "
        f"Diet: {_diet_label(profile)}"
    )


def _render_workout_plan(plan):
    if not plan or not plan.get("days"):
        return "No workout plan has been generated yet - the dashboard's Today's Workout card just shows a 'Generate My Plan' button."
    lines = []
    for day in plan["days"]:
        workout = day.get("workout", {})
        if workout.get("is_rest"):
            line = f"{day['day']}: Rest day."
        else:
            exercises = ", ".join(f"{e['name']} {e['sets_reps']}" for e in workout.get("exercises", []))
            line = f"{day['day']}: {exercises}"
        if day.get("notes"):
            line += f" (Note: {day['notes']})"
        lines.append(line)
    return "\n".join(lines)


def _render_meal_plan(plan):
    if not plan or not plan.get("days"):
        return "No meal plan has been generated yet - the dashboard's Meal Prep card just shows a 'Generate My Plan' button."
    lines = [f"Daily target: ~{plan.get('dailyCalories')} kcal, ~{plan.get('dailyProteinG')}g protein."]
    for day in plan["days"]:
        meals = day.get("meals", {})
        line = (
            f"{day['day']}: Breakfast: {meals.get('breakfast', '')} | Lunch: {meals.get('lunch', '')} | "
            f"Dinner: {meals.get('dinner', '')} | Snack: {meals.get('snack', '')}"
        )
        if day.get("notes"):
            line += f" (Note: {day['notes']})"
        lines.append(line)
    return "\n".join(lines)


def _make_list_past_reports():
    def list_past_reports() -> list[dict]:
        """Lists the user's previously generated injury-risk reports, newest first,
        with each report's filename and creation time (unix seconds). Call this before
        read_report if you need to figure out which report to open - never guess a
        filename.
        """
        os.makedirs(REPORTS_DIR, exist_ok=True)
        entries = []
        for filename in os.listdir(REPORTS_DIR):
            if filename.endswith(".pdf"):
                full_path = os.path.join(REPORTS_DIR, filename)
                entries.append({"filename": filename, "created_at": os.path.getmtime(full_path)})
        entries.sort(key=lambda e: e["created_at"], reverse=True)
        return entries

    return list_past_reports


def _make_read_report():
    def read_report(filename: str) -> str:
        """Reads the full text of one of the user's past injury-risk report PDFs, so
        you can answer questions about what a past workout/report said. `filename`
        must be exactly one returned by list_past_reports.
        """
        safe_name = os.path.basename(filename)
        full_path = os.path.join(REPORTS_DIR, safe_name)
        if not safe_name.endswith(".pdf") or not os.path.isfile(full_path):
            return "That report could not be found - double check the filename from list_past_reports."
        reader = PdfReader(full_path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    return read_report


def _make_get_recent_faults(session_id):
    def get_recent_form_faults() -> list[dict]:
        """Checks for form faults logged so far in the user's CURRENT/most recent
        workout session, if any are still pending. Generating an injury report clears
        this log, so an empty result usually means either no workout has happened yet
        this visit or its report was already generated - it is NOT a full history of
        every fault ever detected (use list_past_reports/read_report for older ones).
        """
        if not session_id:
            return []
        rows = get_faults(session_id)
        return [{"exercise": mode, "fault": message} for mode, message, _ts in rows]

    return get_recent_form_faults


def search_fitness_knowledge(query: str) -> str:
    """Searches this app's curated fitness/nutrition knowledge base (exercise form
    guides, training-split strategies, and government/university/NIH-sourced nutrition
    and workout references) for content relevant to `query`. Use this to ground
    fitness/nutrition answers in real sources instead of general knowledge alone.
    """
    chunks = retrieve(query, k=5)
    return "\n\n---\n\n".join(c["text"] for c in chunks)


def _make_generate_new_workout_plan(profile):
    def generate_new_workout_plan() -> dict:
        """Generates a brand new 7-day WORKOUT plan for the user (no meals), using their
        saved height/weight/age/sex/goal, and REPLACES the one currently shown on their
        dashboard. SLOW (can take up to ~30 seconds) and calls a paid LLM - only call
        this when the user explicitly asks to create/regenerate their workout plan, not
        just to answer a question about the existing one (that's already in context above).
        """
        if not profile or not profile.get("heightCm") or not profile.get("weightKg"):
            return {"error": "No profile saved - tell the user to fill out the Profile card on the dashboard first."}
        return generate_workout_plan(
            profile["heightCm"], profile["weightKg"], profile.get("age", 30),
            (profile.get("sex") or "MALE").upper(), (profile.get("goal") or "MAINTAIN").upper(),
        )

    return generate_new_workout_plan


def _make_generate_new_meal_plan(profile):
    def generate_new_meal_plan() -> dict:
        """Generates a brand new 7-day MEAL plan for the user (no workouts), using their
        saved height/weight/age/sex/goal/diet, and REPLACES the one currently shown on
        their dashboard. SLOW (can take up to ~30 seconds) and calls a paid LLM - only
        call this when the user explicitly asks to create/regenerate their meal plan,
        not just to answer a question about the existing one (that's already in context
        above).
        """
        if not profile or not profile.get("heightCm") or not profile.get("weightKg"):
            return {"error": "No profile saved - tell the user to fill out the Profile card on the dashboard first."}
        diet_category = "NON_VEG" if profile.get("diet") == "NON_VEG" else (
            "VEG_EGGS" if profile.get("eatsEggs") else "VEG_NO_EGGS"
        )
        return generate_meal_plan(
            profile["heightCm"], profile["weightKg"], profile.get("age", 30),
            (profile.get("sex") or "MALE").upper(), (profile.get("goal") or "MAINTAIN").upper(), diet_category,
        )

    return generate_new_meal_plan


def create_chat_session(profile, session_id, workout_plan=None, meal_plan=None):
    """One stateful Gemini chat per WS connection - remembers the conversation across
    turns and has tool access scoped to this specific user's profile/session. The
    already-generated workout/meal plans (whatever's currently cached on the dashboard,
    if anything) are baked into the system instruction once here rather than fetched via
    a tool, so "what should I eat today" is answered directly instead of assuming nothing
    has been generated yet.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set - add it to a .env file before using the coach chat.")

    tools = [
        _make_list_past_reports(),
        _make_read_report(),
        _make_get_recent_faults(session_id),
        search_fitness_knowledge,
        _make_generate_new_workout_plan(profile),
        _make_generate_new_meal_plan(profile),
    ]
    now = datetime.now()
    system_instruction = SYSTEM_INSTRUCTION_TEMPLATE.format(
        today=now.strftime("%Y-%m-%d"),
        today_weekday=now.strftime("%A"),
        profile_context=_profile_context(profile),
        workout_plan_context=_render_workout_plan(workout_plan),
        meal_plan_context=_render_meal_plan(meal_plan),
    )
    config = types.GenerateContentConfig(tools=tools, system_instruction=system_instruction)
    client = genai.Client(api_key=api_key)
    chat = client.chats.create(model=GEMINI_MODEL, config=config)
    # Chat doesn't keep its parent Client alive - if `client` were just a local here, it
    # gets garbage-collected once this function returns (closing the httpx connection
    # `chat` still needs), and the very next send_message fails with a confusing
    # "client has been closed" error. Returning both forces the caller to hold a
    # reference to `client` for as long as `chat` is in use.
    return client, chat


def send_chat_message(chat, message):
    return chat.send_message(message).text
