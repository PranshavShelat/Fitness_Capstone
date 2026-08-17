import json
import os
import re

from google import genai

from rag import retrieve_plan_context

GEMINI_MODEL = "gemini-2.5-flash"

# The full golden_dataset exercise catalog, not just the 10 the app can give live camera
# feedback on - a workout PLAN is a broader recommendation than what the real-time form
# checker happens to support, so it draws from every exercise this project has reference
# movement data for.
PLANNABLE_EXERCISES = [
    "Squats", "Planks", "Tricep Dips", "Pushups", "Pullups",
    "Russian Twists", "Bicep Curls", "Hammer Curls", "Lateral Raises", "Shoulder Press",
    "Bench Press", "Chest Fly Machine", "Deadlift", "Decline Bench Press", "Hip Thrust",
    "Inclined Bench Press", "Lat Pulldown", "Leg Extension", "Leg Raises",
    "Romanian Deadlift", "T-Bar Row", "Tricep Pushdown",
]

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

DIET_TITLES = {
    "VEG_EGGS": "Vegetarian (eats eggs)",
    "VEG_NO_EGGS": "Vegetarian (no eggs)",
    "NON_VEG": "Non-Vegetarian",
}

# Deliberately blunt and repeated (title + a dedicated rule) rather than one soft mention -
# this is a strict dietary requirement, not a preference, and a diet slip in a meal plan is
# a much worse failure than a slightly-off rep scheme.
DIET_RULES = {
    "VEG_EGGS": (
        "The user is VEGETARIAN. Every meal must STRICTLY contain NO meat, poultry, or fish of any "
        "kind, including as a hidden or minor ingredient. Eggs and dairy are allowed."
    ),
    "VEG_NO_EGGS": (
        "The user is VEGETARIAN AND DOES NOT EAT EGGS. Every meal must STRICTLY contain NO meat, "
        "poultry, fish, or eggs of any kind, including as a hidden or minor ingredient. Dairy is allowed."
    ),
    "NON_VEG": "The user is non-vegetarian - meat, poultry, fish, eggs, and dairy may all be used freely.",
}


def bmi_category(bmi):
    if bmi < 18.5:
        return "Underweight"
    if bmi < 25:
        return "Normal"
    if bmi < 30:
        return "Overweight"
    return "Obese"


# Protein targets are the midpoint of the g/kg ranges already documented in
# nutrition/cut_nutrition.txt, maintain_nutrition.txt, and bulk_nutrition.txt.
PROTEIN_G_PER_KG = {"CUT": 2.0, "MAINTAIN": 1.7, "BULK": 1.8}

# Deficit/surplus applied to a rough maintenance estimate, matching the "roughly 15-20%
# deficit" / "roughly 10-15% surplus" language in the same nutrition docs.
CALORIE_ADJUSTMENT = {"CUT": 0.825, "MAINTAIN": 1.0, "BULK": 1.125}


def _daily_targets(weight_kg, goal, bmi_cat):
    """Rough daily calorie + protein targets, computed directly from the user's own
    weight/goal/BMI rather than left for the model to invent - so portion sizes actually
    scale with the person instead of being a fixed "here's a chicken breast" every time.
    Calories use a simple bodyweight-based estimate (no age/sex on file, so this is
    deliberately an approximation, not a precise TDEE) at ~30 kcal/kg maintenance - a
    common quick estimate for a moderately active adult.
    bmi_underweight.txt/bmi_overweight_obese.txt both say a goal-driven deficit/surplus
    is inappropriate at those BMI extremes - that caution is applied here too, not just
    mentioned in passing, by falling back to a maintenance-level calorie target instead.
    """
    maintenance_kcal = weight_kg * 30

    bmi_makes_goal_risky = (
        (goal == "CUT" and bmi_cat == "Underweight")
        or (goal == "BULK" and bmi_cat in ("Overweight", "Obese"))
    )
    adjustment = 1.0 if bmi_makes_goal_risky else CALORIE_ADJUSTMENT[goal]

    calories = round(maintenance_kcal * adjustment / 50) * 50
    protein_g = round(weight_kg * PROTEIN_G_PER_KG[goal] / 5) * 5
    return calories, protein_g


def _build_prompt(height_cm, weight_kg, goal, bmi, category, diet_category, context_chunks, calories, protein_g):
    context_block = "\n\n".join(context_chunks)
    return f"""You are a knowledgeable, encouraging fitness and nutrition coach. Build a full 7-day \
workout and meal plan for a user with these stats:
- Height: {height_cm} cm, Weight: {weight_kg} kg, BMI: {bmi:.1f} ({category})
- Goal: {goal.title()}
- Diet: {DIET_TITLES[diet_category]}
- Estimated daily target: ~{calories} kcal, ~{protein_g}g protein (derived from this user's own \
bodyweight and goal - use it to size portions, not as a rigid exact number)

Use the following reference material as the basis for your plan - stay consistent with the rep \
ranges, split structure, and nutrition/diet guidance it describes:

{context_block}

Rules:
- {DIET_RULES[diet_category]} This is a strict, non-negotiable requirement - re-check every single \
meal against it before finalizing.
- The workout plan may ONLY use exercises from this exact list (every exercise this app has \
reference movement data for): {", ".join(PLANNABLE_EXERCISES)}. Do not invent or substitute any \
other exercise.
- Use a genuinely wide spread of that list across the week - do not repeatedly lean on the same \
small handful of exercises. Any leg-focused day specifically must include at least one quad-dominant \
lift (Squats or Leg Extension), one hamstring/glute-dominant lift (Deadlift, Romanian Deadlift, or \
Hip Thrust), and core work (Planks, Russian Twists, or Leg Raises) - never just one or two exercises \
carrying the entire day. If the plan repeats the same day structure more than once in the week (e.g. \
a 6-day cycle), vary which specific exercises fill each day's slots between repeats rather than \
listing the identical exercises both times.
- Every day of the week must appear, in order (Monday-Sunday). Rest days are allowed and should say so.
- For each training day, list 4-6 exercises with a specific set x rep scheme (e.g. "3x12").
- For each day, also give a short meal plan: breakfast, lunch, dinner, and one snack. Every single \
food item in every meal MUST include a specific, realistic quantity (grams, ounces, cups, or a \
count - e.g. "150g grilled chicken breast", "1 cup cooked rice", "2 whole eggs", "30g almonds"). \
Never list a food with no amount. Size the day's total portions to roughly reach the calorie and \
protein target above, distributed across meals following whatever meal pattern (number of meals, \
snack frequency) the reference material describes for this goal.
- Add one short "notes" string per day only if there's something genuinely useful to flag for that \
specific day (e.g. a BMI-driven caution); otherwise leave it as an empty string.

Respond with ONLY valid JSON, no markdown code fences, no commentary, matching exactly this shape:
{{
  "days": [
    {{
      "day": "Monday",
      "workout": {{"is_rest": false, "exercises": [{{"name": "Squats", "sets_reps": "3x15"}}]}},
      "meals": {{"breakfast": "...", "lunch": "...", "dinner": "...", "snack": "..."}},
      "notes": ""
    }}
  ]
}}"""


def _call_gemini(prompt):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set - add it to a .env file before generating a plan.")
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    return response.text


def _parse_plan_json(response_text):
    text = (response_text or "").strip()
    # Gemini sometimes wraps JSON in a ```json ... ``` fence despite being told not to -
    # strip that instead of letting a formatting slip break the whole plan.
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    data = json.loads(text)

    days_by_name = {d["day"]: d for d in data.get("days", []) if d.get("day")}
    ordered_days = []
    for day_name in DAYS:
        day = days_by_name.get(day_name)
        if day:
            ordered_days.append(day)
    return {"days": ordered_days}


def generate_plan(height_cm, weight_kg, goal, diet_category):
    """Full RAG flow: compute BMI, retrieve goal/BMI/diet-conditioned knowledge base context,
    ask Gemini to synthesize a structured 7-day workout+meal plan grounded in that context,
    and parse the result back into a plain dict.
    """
    height_m = height_cm / 100
    bmi = weight_kg / (height_m * height_m)
    category = bmi_category(bmi)

    calories, protein_g = _daily_targets(weight_kg, goal, category)

    context_chunks, sources = retrieve_plan_context(goal, category, diet_category)
    prompt = _build_prompt(
        height_cm, weight_kg, goal, bmi, category, diet_category, context_chunks, calories, protein_g
    )
    response_text = _call_gemini(prompt)
    plan = _parse_plan_json(response_text)

    return {
        "bmi": round(bmi, 1),
        "bmiCategory": category,
        "goal": goal,
        "diet": diet_category,
        "dailyCalories": calories,
        "dailyProteinG": protein_g,
        "days": plan["days"],
        "sources": sources,
    }
