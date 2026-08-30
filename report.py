import os
import re
from datetime import datetime

from fpdf import FPDF
from google import genai

from db import get_faults, delete_faults
from injury_knowledge import MISHAP_EXPLANATIONS
from anatomy_diagram import render_fault_diagram
from plan import bmi_category

GEMINI_MODEL = "gemini-2.5-flash"
SECTION_MARKER = "===FAULT_{}==="
REPORTS_DIR = "reports"

# Mirrors the exercise list in WorkoutView.jsx - rep_counts/mode strings come from there,
# so the PDF should read the same friendly names the user actually clicked on.
MODE_LABELS = {
    "SQUAT": "Squats", "PLANK": "Planks", "DIP": "Tricep Dips", "PUSHUP": "Pushups",
    "PULLUP": "Pullups", "TWIST": "Russian Twists", "BICEP": "Bicep Curls",
    "HAMMER": "Hammer Curls", "LATERAL": "Lateral Raises", "PRESS": "Shoulder Press",
}


def summarize_faults(rows):
    """rows: list of (mode, message, occurred_at) tuples from db.get_faults.
    Groups by (mode, message) so the same message on two different exercises
    (e.g. "TUCK ELBOWS IN" on both Bicep and Hammer curls) is tracked separately.
    Keeps an internal `count` used only to pick sort order - never surfaced in
    the prompt or PDF text, since per-frame occurrence counts are noisy and
    don't mean what they look like.
    """
    counts = {}
    for mode, message, _occurred_at in rows:
        key = (mode, message)
        counts[key] = counts.get(key, 0) + 1

    summary = []
    for (mode, message), count in counts.items():
        info = MISHAP_EXPLANATIONS.get(message, {})
        summary.append({
            "mode": mode,
            "message": message,
            "count": count,
            "label": info.get("label", message.title()),
            "explanation": info.get("explanation", ""),
            "image": info.get("image"),
            "region": info.get("region"),
        })
    summary.sort(key=lambda fault: fault["count"], reverse=True)
    return summary


def build_gemini_prompt(fault_summary):
    lines = [
        "You are a knowledgeable, encouraging fitness coach writing a short injury-risk "
        "report for a user's workout. You are given a list of form faults detected during "
        "their session, along with the known biomechanical risk each fault carries. Write "
        "one clear, plain-English paragraph per fault explaining what happened and what it "
        "could lead to if uncorrected. Do not state or imply how many times it happened - "
        "just describe it generally (e.g. 'this happened during your set'), since exact "
        "per-frame counts aren't meaningful to the user. Be direct and factual, not "
        "alarmist. Do not invent risks beyond what's described below. Address the user "
        "directly as 'you'. Plain text only, no markdown formatting.",
        "",
        "Faults detected this session:",
    ]
    for i, fault in enumerate(fault_summary):
        lines.append(f'{i}. {fault["mode"]} - "{fault["label"]}": {fault["explanation"]}')
    lines.append("")
    lines.append(
        "Respond with exactly one paragraph per fault listed above, in the same order. "
        "Before each paragraph, put a line by itself with exactly this text (i is the "
        "fault's number above): " + SECTION_MARKER.format("i")
    )
    return "\n".join(lines)


def call_gemini(prompt):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set - add it to a .env file before generating a report.")
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    return response.text


def _diet_label(profile):
    if profile.get("diet") == "NON_VEG":
        return "Non-Vegetarian"
    return "Vegetarian (eats eggs)" if profile.get("eatsEggs") else "Vegetarian (no eggs)"


def build_health_summary_prompt(profile, bmi, category):
    return f"""You are a knowledgeable, encouraging fitness coach. A user just finished a workout. \
Write ONE short paragraph (2-4 sentences) giving them brief, practical health context based on \
their stats below - general context for their BMI category and stated goal, not a diagnosis. Be \
direct and factual, not alarmist. Address the user directly as 'you'. Plain text only, no markdown \
formatting, no headers or labels - just the paragraph itself.

User stats: BMI {bmi:.1f} ({category}), Age: {profile.get('age')}, Sex: {(profile.get('sex') or '').title()}, \
Goal: {(profile.get('goal') or '').title()}, Diet: {_diet_label(profile)}."""


def generate_health_summary(profile, bmi, category):
    prompt = build_health_summary_prompt(profile, bmi, category)
    return call_gemini(prompt).strip()


def split_gemini_sections(response_text, n):
    """Parses the ===FAULT_i=== delimited response back into a list of n paragraphs,
    in order. Falls back to the curated explanation for any section that's missing
    or if the model didn't follow the delimiter format (never let a formatting slip
    break the report).
    """
    sections = [None] * n
    pattern = re.compile(r"===FAULT_(\d+)===\s*(.*?)(?=(?:===FAULT_\d+===)|\Z)", re.DOTALL)
    for match in pattern.finditer(response_text or ""):
        idx = int(match.group(1))
        if 0 <= idx < n:
            sections[idx] = match.group(2).strip()
    return sections


def _line(pdf, h, text):
    # multi_cell(w=0, ...) leaves the x-cursor at the right margin instead of
    # resetting it to the left margin, so the *next* multi_cell call sees ~zero
    # horizontal space left and raises FPDFException. Reset x before every call.
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, h, text)


def render_pdf(duration_seconds, rep_counts, plank_hold_seconds, fault_summary, fault_paragraphs, health_context=None):
    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    _line(pdf, 12, "Workout Injury Risk Report")

    pdf.set_font("Helvetica", "", 10)
    _line(pdf, 8, datetime.now().strftime("%Y-%m-%d %H:%M"))
    pdf.ln(4)

    if health_context:
        pdf.set_font("Helvetica", "B", 13)
        _line(pdf, 10, "Health Summary")
        pdf.set_font("Helvetica", "", 11)
        _line(pdf, 7, f"BMI {health_context['bmi']:.1f} ({health_context['category']}) - Goal: {health_context['goal']}")
        pdf.ln(1)
        _line(pdf, 7, health_context["summary"])
        pdf.ln(4)

    pdf.set_font("Helvetica", "B", 13)
    _line(pdf, 10, "Workout Summary")
    pdf.set_font("Helvetica", "", 11)
    minutes, seconds = divmod(int(duration_seconds), 60)
    _line(pdf, 7, f"Duration: {minutes:02d}:{seconds:02d}")
    pdf.ln(2)

    exercise_lines = [
        f"{MODE_LABELS.get(mode, mode.title())}: {count} reps"
        for mode, count in (rep_counts or {}).items() if count
    ]
    if plank_hold_seconds:
        exercise_lines.append(f"Planks: {round(plank_hold_seconds)}s held")

    pdf.set_font("Helvetica", "B", 11)
    _line(pdf, 7, "Exercises Completed")
    pdf.set_font("Helvetica", "", 11)
    if exercise_lines:
        for line in exercise_lines:
            _line(pdf, 7, f"- {line}")
    else:
        _line(pdf, 7, "No exercises were tracked this session.")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 13)
    _line(pdf, 10, "Mishaps & Injury Risk")

    if not fault_summary:
        pdf.set_font("Helvetica", "", 11)
        _line(pdf, 7, "No risky form issues were detected during this workout. Great job!")
    else:
        for fault, paragraph in zip(fault_summary, fault_paragraphs):
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 12)
            _line(pdf, 8, fault["label"])

            if fault["image"] and fault["region"]:
                diagram = render_fault_diagram(fault["image"], fault["region"], fault["label"])
                pdf.set_x(pdf.l_margin)
                pdf.image(diagram, w=80)

            pdf.set_font("Helvetica", "", 11)
            _line(pdf, 7, paragraph or fault["explanation"])

    return bytes(pdf.output())


def generate_report_pdf(session_id, duration_seconds, rep_counts, plank_hold_seconds, profile=None):
    """Full flow: read this session's logged faults, summarize them, optionally ask
    Gemini to write the explanatory prose, render the PDF, then wipe the session's
    rows from the mishap log (per design: it's a scratch log, the PDF is the record).
    `profile` is the same {heightCm, weightKg, age, sex, goal, diet, eatsEggs} dict
    Dashboard.jsx saves to localStorage - if present, a Health Summary section is added.
    Returns (filename, pdf_bytes).
    """
    rows = get_faults(session_id)
    fault_summary = summarize_faults(rows)

    if fault_summary:
        prompt = build_gemini_prompt(fault_summary)
        response_text = call_gemini(prompt)
        fault_paragraphs = split_gemini_sections(response_text, len(fault_summary))
    else:
        fault_paragraphs = []

    health_context = None
    if profile and profile.get("heightCm") and profile.get("weightKg"):
        height_m = profile["heightCm"] / 100
        bmi = profile["weightKg"] / (height_m * height_m)
        category = bmi_category(bmi)
        health_context = {
            "bmi": bmi,
            "category": category,
            "goal": (profile.get("goal") or "").title(),
            "summary": generate_health_summary(profile, bmi, category),
        }

    pdf_bytes = render_pdf(duration_seconds, rep_counts, plank_hold_seconds, fault_summary, fault_paragraphs, health_context)

    delete_faults(session_id)

    filename = f"workout_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    os.makedirs(REPORTS_DIR, exist_ok=True)
    with open(os.path.join(REPORTS_DIR, filename), "wb") as f:
        f.write(pdf_bytes)

    return filename, pdf_bytes
