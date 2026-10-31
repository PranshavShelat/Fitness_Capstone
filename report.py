import json
import os
import re
from datetime import datetime

from fpdf import FPDF
from gemini_util import generate

from db import get_fault_details, delete_faults
from form_reference import (LOW_CONFIDENCE_RATE, checkpoints, describe_measurement, fault_metric,
                            guide_for_mode, reference_false_alarm_rates, source_lines, video_url)
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


# Research-backed risks are listed before manual guidance, and both before
# plain technique tips - the report leads with what matters most.
EVIDENCE_RANK = {"research": 0, "guideline": 1, "coaching": 2}


def _rep_list(reps):
    return ", ".join(str(r) for r in reps)


def summarize_faults(rows, rep_counts=None):
    """rows: (mode, message, occurred_at[, rep_index, measured]) tuples from db.
    Groups by (mode, message). For each fault it works out:
      * which reps it happened on, out of how many the user did - a rep-level
        count IS meaningful (unlike the old per-frame count, which was noise);
      * the worst measured value vs the engine's safe limit;
      * whether it only appeared late in the set (a fatigue pattern);
      * whether the check is low confidence because it also fires on the
        correct reference recording.
    """
    rep_counts = rep_counts or {}
    try:
        false_rates = reference_false_alarm_rates()
    except Exception as e:  # recordings missing etc. - never block the report
        print("Could not compute reference false-alarm rates:", e)
        false_rates = {}

    groups = {}
    for row in rows:
        mode, message = row[0], row[1]
        rep_index = row[3] if len(row) > 3 else None
        measured = row[4] if len(row) > 4 else None
        g = groups.setdefault((mode, message), {"events": 0, "reps": set(), "values": []})
        g["events"] += 1
        if rep_index is not None:
            g["reps"].add(int(rep_index))
        if measured is not None:
            g["values"].append(measured)

    summary = []
    for (mode, message), g in groups.items():
        info = MISHAP_EXPLANATIONS.get(message, {})
        total = int(rep_counts.get(mode) or 0)
        reps = sorted(g["reps"])

        _metric, direction = fault_metric(mode, message)
        worst = None
        if g["values"] and direction:
            worst = min(g["values"]) if direction == "min" else max(g["values"])

        fatigue = (total >= 4 and len(reps) >= 2 and min(reps) > total / 2)
        rate = false_rates.get((mode, message), 0.0)

        summary.append({
            "mode": mode,
            "message": message,
            "count": g["events"],
            "label": info.get("label", message.title()),
            "explanation": info.get("explanation", ""),
            "evidence": info.get("evidence"),
            "prevention": info.get("prevention") or {},
            "sources": info.get("sources") or [],
            "reps": reps,
            "total_reps": total,
            "measurement": describe_measurement(mode, message, worst),
            "fatigue": fatigue,
            "low_confidence": rate >= LOW_CONFIDENCE_RATE,
            "reference_rate": rate,
        })
    summary.sort(key=lambda f: (f["low_confidence"], EVIDENCE_RANK.get(f["evidence"], 3),
                                -len(f["reps"]), -f["count"]))
    return summary


def reps_text(fault):
    """'3 of 10 reps (reps 3, 5, 6)' / 'reps 3, 5' / '' for holds."""
    reps, total = fault.get("reps") or [], fault.get("total_reps") or 0
    if not reps:
        return ""
    counted = [r for r in reps if not total or r <= total]
    unfinished = len(reps) - len(counted)
    if total:
        text = f"{len(counted)} of your {total} {'rep' if total == 1 else 'reps'}"
        if counted:
            text += f" (rep{'s' if len(counted) > 1 else ''} {_rep_list(counted)})"
        if unfinished:
            text += " + an unfinished last rep"
        return text
    return f"rep{'s' if len(reps) > 1 else ''} {_rep_list(reps)}"


def low_confidence_text(fault):
    return ("The camera may have got this one wrong - it sometimes flags this even when the form "
            "is good. Check yourself in a mirror or film a set to be sure. "
            f"(It triggers on {fault['reference_rate'] * 100:.0f}% of our correct-form reference video.)")


def exercise_scorecard(rep_counts, plank_hold_seconds, fault_summary):
    """One line per exercise done: clean reps out of total, and the issues seen."""
    lines = []
    by_mode = {}
    for f in fault_summary:
        by_mode.setdefault(f["mode"], []).append(f)
    modes = [m for m, c in (rep_counts or {}).items() if c]
    if plank_hold_seconds and "PLANK" not in modes:
        modes.append("PLANK")
    for f in fault_summary:  # an exercise with faults but no finished reps still gets a line
        if f["mode"] not in modes:
            modes.append(f["mode"])

    for mode in modes:
        faults = by_mode.get(mode, [])
        total = int((rep_counts or {}).get(mode) or 0)
        name = MODE_LABELS.get(mode, mode.title())
        confident = [f for f in faults if not f["low_confidence"]]
        if total:
            bad = set()
            for f in confident:
                bad.update(r for r in f["reps"] if r <= total)
            clean = total - len(bad)
            head = f"{clean} of {total} reps looked good"
        elif mode == "PLANK":
            head = f"held for {round(plank_hold_seconds or 0)} seconds"
        else:
            head = "no completed reps"
        issues = ", ".join(f["label"] + (" (camera unsure)" if f["low_confidence"] else "") for f in faults)
        lines.append((name, head, issues or "none - nice work"))
    return lines


def build_gemini_prompt(fault_summary):
    lines = [
        "You are a friendly, encouraging fitness coach writing a short workout report for "
        "someone who may be completely new to exercise. You are given a list of form faults "
        "detected during their session, along with what each one means. Write one short "
        "paragraph per fault explaining what happened and why it matters. Write so a "
        "12-year-old could follow it: short sentences, everyday words, no jargon - if a "
        "body part or term needs naming, explain it in brackets. Do not mention studies, "
        "manuals, page numbers or sources by name; those are printed separately. "
        "Where a fault lists the reps it happened on, you may use that exact fact (e.g. "
        "'on 3 of your 10 reps'). Do NOT mention angles, degrees or percentages - the exact "
        "measurements are printed separately for those who want them; your job is the plain "
        "explanation. Never invent numbers. If a fault says it "
        "only appeared in later reps, you may say it showed up as you got tired. If a fault is "
        "marked LOW CONFIDENCE, say gently that the camera may have misread it. Be direct and "
        "factual, not alarmist. Use ONLY the facts in each fault's description below - do not add "
        "risks, statistics, studies, body parts or advice that are not in it, because "
        "every claim in this report must be traceable to a cited source. Do not give "
        "fixes or drills; those are printed separately under each paragraph. Keep each "
        "paragraph to 2-3 sentences. Address the user directly as 'you'. Plain text "
        "only, no markdown formatting.",
        "",
        "Faults detected this session:",
    ]
    for i, fault in enumerate(fault_summary):
        facts = []
        if reps_text(fault):
            facts.append("happened on " + reps_text(fault))
        m = fault.get("measurement")
        if m:
            facts.append(f"worst measured {m['what'].lower()}: {m['value']}, safe limit {m['limit']}")
        if fault.get("fatigue"):
            facts.append("only appeared in the later reps of the set")
        if fault.get("low_confidence"):
            facts.append("LOW CONFIDENCE - this check also fires on correct form")
        extra = f" [Session facts: {'; '.join(facts)}]" if facts else ""
        lines.append(f'{i}. {fault["mode"]} - "{fault["label"]}": {fault["explanation"]}{extra}')
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

    # Form scorecard: what went RIGHT as well as wrong, per exercise.
    pdf.set_font("Helvetica", "B", 11)
    _line(pdf, 7, "How Your Form Looked")
    scorecard = exercise_scorecard(rep_counts, plank_hold_seconds, fault_summary)
    if scorecard:
        for name, head, issues in scorecard:
            _labelled(pdf, f"- {name}: {head}.", f"Issues: {issues}.")
        # One-line verdict a non-lifter can act on.
        total_reps = sum(int(c or 0) for c in (rep_counts or {}).values())
        bad_reps = 0
        for mode, count in (rep_counts or {}).items():
            bad = set()
            for f in fault_summary:
                if f["mode"] == mode and not f["low_confidence"]:
                    bad.update(r for r in f["reps"] if r <= int(count or 0))
            bad_reps += len(bad)
        main = next((f for f in fault_summary if not f["low_confidence"]), None)
        verdict = (f"{total_reps - bad_reps} of your {total_reps} reps looked good. " if total_reps else "")
        verdict += (f"The main thing to work on: {main['label']}." if main
                    else "No clear form problems - keep it up.")
        pdf.ln(1)
        _labelled(pdf, "In one line:", verdict)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(90, 90, 90)
        _line(pdf, 4.5, "A rep looks good when the camera did not flag anything on it. Problems marked "
                        "\"camera unsure\" are listed but not counted against you.")
        pdf.set_text_color(0, 0, 0)
    else:
        pdf.set_font("Helvetica", "", 11)
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
            where = reps_text(fault)
            tag = f" [{where}]" if where else ""
            if fault.get("low_confidence"):
                tag += " [camera unsure]"
            _labelled(pdf, f"- {fault['label']}{tag}:", first)
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

            # Hard numbers from the camera, so the fault is evidence, not a verdict.
            m = fault.get("measurement")
            short = (m or {}).get("plain") or ""
            if reps_text(fault):
                short = (short + " " if short else "") + f"It happened on {reps_text(fault)}."
            if short:
                _labelled(pdf, "In short:", short)
            if m:
                # The specifics, for anyone who wants them - kept small and secondary.
                pdf.set_font("Helvetica", "", 8.5)
                pdf.set_text_color(110, 110, 110)
                _line(pdf, 4.5, f"Details: {m['what'].lower()} reached {m['value']}; "
                                f"the safe range is {m['limit']}.")
                pdf.set_text_color(0, 0, 0)
                pdf.ln(1)
            if fault.get("fatigue"):
                _labelled(pdf, "Pattern:", "This only showed up in the second half of your set, which "
                                           "usually means you were getting tired. End the set a rep or "
                                           "two earlier, or lower the weight.")
            if fault.get("low_confidence"):
                _note(pdf, low_confidence_text(fault))

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

    # The correct form for every exercise done today (form_reference.py) - the
    # same guide shown in the workout planner, with the engine's own numbers.
    done_modes = [m for m, c in (rep_counts or {}).items() if c]
    if plank_hold_seconds and "PLANK" not in done_modes:
        done_modes.append("PLANK")
    for f in fault_summary or []:
        if f["mode"] not in done_modes:
            done_modes.append(f["mode"])
    guide_sources = []
    if done_modes:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 13)
        _line(pdf, 10, "How Each Exercise Should Look")
        pdf.set_font("Helvetica", "", 10)
        _line(pdf, 6, "What good form looks like for each exercise you did today, with a video "
                      "to watch before your next session.")
        for mode in done_modes:
            name, g = guide_for_mode(mode)
            if not g:
                continue
            if pdf.get_y() + 50 > pdf.page_break_trigger:
                pdf.add_page()
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 12)
            _line(pdf, 7, name)
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(90, 90, 90)
            _line(pdf, 5, "Works: " + g["muscles"])
            pdf.set_text_color(0, 0, 0)
            _labelled(pdf, "Set up:", " ".join(g["setup"]))
            _labelled(pdf, "Do it:", " ".join(g["execution"]))
            _labelled(pdf, "Breathing:", g["breathing"])
            url = video_url(name)
            if url:
                pdf.set_x(pdf.l_margin)
                pdf.set_font("Helvetica", "B", 10)
                pdf.write(6, "Watch how it's done: ")
                pdf.set_font("Helvetica", "U", 10)
                pdf.set_text_color(20, 80, 200)
                pdf.write(6, _safe(url.replace("https://", "")), link=url)
                pdf.set_text_color(0, 0, 0)
                pdf.ln(7)
            cps = checkpoints(mode)
            if cps:
                pdf.set_font("Helvetica", "", 8.5)
                pdf.set_text_color(110, 110, 110)
                _line(pdf, 4.5, "For the curious - what the camera checks: " + " ".join(cps))
                pdf.set_text_color(0, 0, 0)
            srcs = source_lines(g)
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(90, 90, 90)
            _line(pdf, 4.5, "Sources: " + ("; ".join(srcs) if srcs else
                                            "standard technique coaching (no specific manual page)"))
            pdf.set_text_color(0, 0, 0)
            guide_sources.extend(k for k, _loc in g["sources"])

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
    for key in [k for _t, k, _l in GENERAL_PREVENTION] + guide_sources:
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
    rows = get_fault_details(session_id)
    fault_summary = summarize_faults(rows, rep_counts)

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
