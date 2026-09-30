import json
import os
import re
from datetime import datetime

from fpdf import FPDF
from gemini_util import generate

from db import get_faults, delete_faults
from injury_knowledge import EVIDENCE_LABELS, GENERAL_PREVENTION, MISHAP_EXPLANATIONS, SOURCES
from plan import bmi_category

# Model names, retries and the backup model live in gemini_util.py.
SECTION_MARKER = "===FAULT_{}==="
REPORTS_DIR = "reports"

# Mirrors the exercise list in WorkoutView.jsx - rep_counts/mode strings come from there,
# so the PDF should read the same friendly names the user actually clicked on.
MODE_LABELS = {
    "SQUAT": "Squats", "PLANK": "Planks", "DIP": "Tricep Dips", "PUSHUP": "Pushups",
    "PULLUP": "Pullups", "TWIST": "Russian Twists", "BICEP": "Bicep Curls",
    "HAMMER": "Hammer Curls", "LATERAL": "Lateral Raises", "PRESS": "Shoulder Press",
    "RDL": "Romanian Deadlift", "HIPTHRUST": "Hip Thrust", "PULLDOWN": "Lat Pulldown",
    "LEGEXT": "Leg Extension", "LEGRAISE": "Leg Raises",
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
            "evidence": info.get("evidence"),
            "prevention": info.get("prevention") or {},
            "sources": info.get("sources") or [],
        })
    summary.sort(key=lambda fault: fault["count"], reverse=True)
    return summary


def build_gemini_prompt(fault_summary):
    lines = [
        "You are a friendly, encouraging fitness coach writing a short workout report for "
        "someone who may be completely new to exercise. You are given a list of form faults "
        "detected during their session, along with what each one means. Write one short "
        "paragraph per fault explaining what happened and why it matters. Write so a "
        "12-year-old could follow it: short sentences, everyday words, no jargon - if a "
        "body part or term needs naming, explain it in brackets. Do not mention studies, "
        "manuals, page numbers or sources by name; those are printed separately. "
        "Do not state or imply how many times it happened - "
        "just describe it generally (e.g. 'this happened during your set'), since exact "
        "per-frame counts aren't meaningful to the user. Be direct and factual, not "
        "alarmist. Use ONLY the facts in each fault's description below - do not add "
        "risks, statistics, studies, body parts or advice that are not in it, because "
        "every claim in this report must be traceable to a cited source. Do not give "
        "fixes or drills; those are printed separately under each paragraph. Keep each "
        "paragraph to 2-3 sentences. Address the user directly as 'you'. Plain text "
        "only, no markdown formatting.",
        "",
        "Faults detected this session:",
    ]
    for i, fault in enumerate(fault_summary):
        lines.append(f'{i}. {fault["mode"]} - "{fault["label"]}": {fault["explanation"]}')
    lines.append("")
    lines.append(
        f"Respond with a JSON array of exactly {len(fault_summary)} strings - one paragraph "
        "per fault listed above, in the same order (element 0 is fault 0). Output only the "
        "JSON array, nothing else."
    )
    return "\n".join(lines)


def call_gemini(prompt, json_output=False):
    return generate(prompt, json_output=json_output, purpose="the report")


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
    """Turns Gemini's reply into a list of n paragraphs (None where missing).

    Expected shape is a JSON array of n strings. Also accepts a JSON object
    holding such an array, a ```json fenced block, and - as a last resort - the
    old ===FAULT_i=== markers in any spacing/case, 0- or 1-based. Anything it
    cannot use stays None so render_pdf falls back to the curated explanation.
    """
    text = (response_text or "").strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            data = next((v for v in data.values() if isinstance(v, list)), None)
        if isinstance(data, list):
            out = [str(x).strip() if isinstance(x, (str, int, float)) and str(x).strip() else None
                   for x in data[:n]]
            return out + [None] * (n - len(out))
    except ValueError:
        pass

    sections = {}
    pattern = re.compile(r"=+\s*\**\s*FAULT[_ ]?(\d+)\s*\**\s*=+\s*(.*?)(?=(?:=+\s*\**\s*FAULT[_ ]?\d+)|\Z)",
                         re.DOTALL | re.IGNORECASE)
    for match in pattern.finditer(text):
        sections[int(match.group(1))] = match.group(2).strip().strip("*").strip() or None
    offset = 1 if sections and 0 not in sections and n in sections else 0
    return [sections.get(i + offset) for i in range(n)]


_UNICODE_FIXES = {
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": " - ", "\u2026": "...", "\u00a0": " ", "\u2022": "-",
}

def _safe(text):
    """fpdf2's core Helvetica font is latin-1 only - one curly quote or em dash
    from Gemini would otherwise crash the whole report. Normalise the common
    ones and replace anything else unencodable."""
    text = str(text or "")
    for bad, good in _UNICODE_FIXES.items():
        text = text.replace(bad, good)
    return text.encode("latin-1", "replace").decode("latin-1")


def _line(pdf, h, text):
    # multi_cell(w=0, ...) leaves the x-cursor at the right margin instead of
    # resetting it to the left margin, so the *next* multi_cell call sees ~zero
    # horizontal space left and raises FPDFException. Reset x before every call.
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, h, _safe(text))


def _labelled(pdf, label, text):
    """'Label: text' with the label in bold, wrapping as one paragraph."""
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 10)
    pdf.write(6, _safe(label + " "))
    pdf.set_font("Helvetica", "", 10)
    pdf.write(6, _safe(text))
    pdf.ln(7)


def _source_line(key, locator):
    src = SOURCES.get(key, {})
    return f"{src.get('short', key)}, {locator}" if locator else src.get("short", key)


AI_UNAVAILABLE_NOTE = ("AI summary unavailable - showing the standard explanations. "
                       "The advice and sources below are unchanged.")


def _note(pdf, text):
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(150, 90, 0)
    _line(pdf, 5, text)
    pdf.set_text_color(0, 0, 0)


def render_pdf(duration_seconds, rep_counts, plank_hold_seconds, fault_summary, fault_paragraphs,
               health_context=None, ai_unavailable=False):
    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    _line(pdf, 12, "Your Workout Form Report")

    pdf.set_font("Helvetica", "", 10)
    _line(pdf, 8, datetime.now().strftime("%Y-%m-%d %H:%M"))
    pdf.ln(4)

    if health_context:
        pdf.set_font("Helvetica", "B", 13)
        _line(pdf, 10, "Health Summary")
        pdf.set_font("Helvetica", "", 11)
        _line(pdf, 7, f"BMI {health_context['bmi']:.1f} ({health_context['category']}) - Goal: {health_context['goal']}")
        if health_context.get("summary"):
            pdf.ln(1)
            _line(pdf, 7, health_context["summary"])
        else:
            _note(pdf, "AI health summary unavailable for this report.")
        pdf.ln(4)

    pdf.set_font("Helvetica", "B", 13)
    _line(pdf, 10, "Workout Summary")
    pdf.set_font("Helvetica", "", 11)
    minutes, seconds = divmod(int(duration_seconds), 60)
    _line(pdf, 7, f"Duration: {minutes:02d}:{seconds:02d}")
    pdf.ln(2)

    exercise_lines = [
        f"{MODE_LABELS.get(mode, mode.title())}: {count} {'rep' if count == 1 else 'reps'}"
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

    # "At a Glance": everything a reader needs in a few lines - the problems
    # found and the one thing to do about each. Details follow below.
    if fault_summary:
        pdf.set_font("Helvetica", "B", 13)
        _line(pdf, 10, "At a Glance")
        pdf.set_font("Helvetica", "", 11)
        n = len(fault_summary)
        _line(pdf, 7, f"We spotted {n} form {'issue' if n == 1 else 'issues'} in this workout. "
                      "Here is the quick version; the details are further down.")
        pdf.ln(1)
        for fault in fault_summary:
            fix = (fault.get("prevention") or {}).get("fix", "")
            first = fix.split(". ")[0].rstrip(".") + "." if fix else ""
            _labelled(pdf, f"- {fault['label']}:", first)
        pdf.ln(3)

    pdf.set_font("Helvetica", "B", 13)
    _line(pdf, 10, "Form Issues in Detail")

    if not fault_summary:
        pdf.set_font("Helvetica", "", 11)
        _line(pdf, 7, "No risky form issues were detected during this workout. Great job!")
    else:
        # Visible, so a broken Gemini key/quota/model is noticed instead of
        # silently producing a slightly different report.
        if ai_unavailable or any(p is None for p in fault_paragraphs):
            _note(pdf, AI_UNAVAILABLE_NOTE)
        for fault, paragraph in zip(fault_summary, fault_paragraphs):
            # Keep a heading with the start of its text instead of stranding it
            # at the bottom of a page.
            if pdf.get_y() + 45 > pdf.page_break_trigger:
                pdf.add_page()

            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 12)
            _line(pdf, 8, fault["label"])
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(90, 90, 90)
            meta = f"Exercise: {MODE_LABELS.get(fault['mode'], str(fault['mode']).title())}"
            if fault.get("evidence") in EVIDENCE_LABELS:
                meta += "   |   How sure we are: " + EVIDENCE_LABELS[fault["evidence"]]
            _line(pdf, 5, meta)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(1)

            pdf.set_font("Helvetica", "B", 11)
            _line(pdf, 7, "What happened")
            pdf.set_font("Helvetica", "", 11)
            _line(pdf, 6.5, paragraph or fault["explanation"])

            # Prevention is printed verbatim from injury_knowledge.py (not via
            # Gemini) so the advice is exactly what the cited sources support.
            prevention = fault.get("prevention") or {}
            if prevention:
                pdf.ln(1)
                pdf.set_font("Helvetica", "B", 11)
                _line(pdf, 7, "How to fix it")
                if prevention.get("fix"):
                    _labelled(pdf, "Next time:", prevention["fix"])
                if prevention.get("drill"):
                    _labelled(pdf, "Exercise that helps:", prevention["drill"])
                if prevention.get("progression"):
                    _labelled(pdf, "Going forward:", prevention["progression"])

            if fault.get("sources"):
                pdf.set_font("Helvetica", "I", 8)
                pdf.set_text_color(90, 90, 90)
                _line(pdf, 4.5, "Sources: " + "; ".join(_source_line(k, loc) for k, loc in fault["sources"]))
                pdf.set_text_color(0, 0, 0)
            pdf.ln(2)

    # General, sourced prevention advice - useful after any session.
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 13)
    _line(pdf, 10, "Tips to Stay Injury-Free")
    for text, _key, _locator in GENERAL_PREVENTION:
        pdf.set_font("Helvetica", "", 10.5)
        _line(pdf, 6, f"- {text}")
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(90, 90, 90)
    _line(pdf, 4.5, "Sources: " + "; ".join(_source_line(k, loc) for _t, k, loc in GENERAL_PREVENTION))
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    # Full references for every source cited anywhere in this report.
    used = []
    for fault in fault_summary or []:
        for key, _loc in fault.get("sources") or []:
            if key not in used:
                used.append(key)
    for _text, key, _loc in GENERAL_PREVENTION:
        if key not in used:
            used.append(key)
    pdf.set_font("Helvetica", "B", 13)
    _line(pdf, 10, "References")
    for i, key in enumerate(used, 1):
        src = SOURCES[key]
        pdf.set_font("Helvetica", "", 8)
        _line(pdf, 4.5, f"[{i}] {src['full']} ({src['type']})")
    pdf.ln(2)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(90, 90, 90)
    _line(pdf, 4.5, "This report gives general exercise-technique guidance based on the sources above. "
                    "It is not a medical diagnosis. If you have pain, especially sharp or lasting pain, "
                    "stop the exercise and see a doctor or physiotherapist.")
    pdf.set_text_color(0, 0, 0)

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

    # Gemini only rewrites the explanation into friendlier prose. If it is
    # unavailable (no key, no network, quota, bad model name) the report still
    # generates with the curated explanations - a demo must never hinge on it.
    fault_paragraphs = [None] * len(fault_summary)
    ai_unavailable = False
    if fault_summary:
        try:
            response_text = call_gemini(build_gemini_prompt(fault_summary), json_output=True)
            fault_paragraphs = split_gemini_sections(response_text, len(fault_summary))
            if any(p is None for p in fault_paragraphs):
                # Keep the evidence: without the raw reply there is no way to
                # tell a formatting slip from a truncated or refused answer.
                print("Gemini reply could not be fully parsed "
                      f"({sum(p is None for p in fault_paragraphs)}/{len(fault_paragraphs)} missing). "
                      f"Raw reply (first 800 chars):\n{(response_text or '')[:800]}")
        except Exception as e:
            ai_unavailable = True
            print("Gemini unavailable for the fault paragraphs, using curated text:", e)

    health_context = None
    if profile and profile.get("heightCm") and profile.get("weightKg"):
        height_m = profile["heightCm"] / 100
        bmi = profile["weightKg"] / (height_m * height_m)
        category = bmi_category(bmi)
        try:
            summary = generate_health_summary(profile, bmi, category)
        except Exception as e:
            print("Gemini unavailable for the health summary, skipping it:", e)
            summary = None
        health_context = {
            "bmi": bmi,
            "category": category,
            "goal": (profile.get("goal") or "").title(),
            "summary": summary,
        }

    pdf_bytes = render_pdf(duration_seconds, rep_counts, plank_hold_seconds, fault_summary, fault_paragraphs,
                           health_context, ai_unavailable)

    delete_faults(session_id)

    filename = f"workout_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    os.makedirs(REPORTS_DIR, exist_ok=True)
    with open(os.path.join(REPORTS_DIR, filename), "wb") as f:
        f.write(pdf_bytes)

    return filename, pdf_bytes
