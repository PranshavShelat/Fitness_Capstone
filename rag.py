import glob
import os

import numpy as np
from sentence_transformers import SentenceTransformer

from pdf_knowledge import load_pdf_chunks

KNOWLEDGE_DIR = "knowledge_base"
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
CACHE_PATH = "knowledge_base_embeddings.npz"

GOAL_LABELS = {"CUT": "cutting fat loss", "MAINTAIN": "maintaining stable weight", "BULK": "bulking muscle gain"}

# Diet docs differ mainly in one subtle detail ("eats eggs" vs "no eggs"), which the small
# embedding model can't reliably discriminate (validated empirically: VEG_EGGS and
# VEG_NO_EGGS queries produced the identical ranking). Unlike the goal/BMI queries above,
# diet is an exact field the user already picked explicitly, not free text to interpret -
# so it's looked up by filename instead of guessed at via similarity.
DIET_FILES = {
    "VEG_EGGS": "diet/vegetarian_with_eggs.txt",
    "VEG_NO_EGGS": "diet/vegetarian_no_eggs.txt",
    "NON_VEG": "diet/non_vegetarian.txt",
}

# Friendly citation labels for the hand-written knowledge_base/*.txt docs (excluding
# exercises/, which cites as one combined line - see _dedupe_sources).
TXT_SOURCE_TITLES = {
    "splits/cut_split.txt": "Cutting — Weekly Training Split Guide",
    "splits/maintain_split.txt": "Maintenance — Weekly Training Split Guide",
    "splits/bulk_split.txt": "Bulking — Weekly Training Split Guide",
    "nutrition/cut_nutrition.txt": "Cutting — Nutrition Strategy Guide",
    "nutrition/maintain_nutrition.txt": "Maintenance — Nutrition Strategy Guide",
    "nutrition/bulk_nutrition.txt": "Bulking — Nutrition Strategy Guide",
    "nutrition/bmi_underweight.txt": "Underweight BMI — Nutrition Caution Guide",
    "nutrition/bmi_overweight_obese.txt": "Overweight/Obese BMI — Nutrition Caution Guide",
    "diet/vegetarian_with_eggs.txt": "Vegetarian (Eats Eggs) — Diet Guide",
    "diet/vegetarian_no_eggs.txt": "Vegetarian (No Eggs) — Diet Guide",
    "diet/non_vegetarian.txt": "Non-Vegetarian — Diet Guide",
}

# Friendly citation labels for the downloaded PDFs - the real institutional title/source,
# since prettifying the filename alone ("Cut Vcu Weight Loss Guide") loses exactly the
# citation value the user is asking for.
PDF_SOURCE_TITLES = {
    "source_pdfs/nutrition/cut_vcu_weight_loss_guide.pdf":
        "VCU Student Health — A Practical Guide to Healthy Weight Loss",
    "source_pdfs/nutrition/maintain_dietary_guidelines_for_americans_2020-2025.pdf":
        "Dietary Guidelines for Americans, 2020-2025 (USDA/HHS)",
    "source_pdfs/nutrition/bulk_fit100_muscle_gain_nutrition_guide.pdf":
        "FIT 100 Muscle Gain Nutrition Guide",
    "source_pdfs/nutrition/bmi_nih_practical_guide_obesity.pdf":
        "NIH NHLBI — Practical Guide to the Identification and Treatment of Obesity",
    "source_pdfs/nutrition/bmi_nih_dietary_treatment_of_obesity.pdf":
        "NIH/Endotext — Dietary Treatment of Obesity",
    "source_pdfs/workouts/general_army_fm7-22_physical_readiness_training.pdf":
        "U.S. Army FM 7-22 — Physical Readiness Training",
    "source_pdfs/workouts/maintain_hhs_physical_activity_guidelines_2nd_edition.pdf":
        "Physical Activity Guidelines for Americans, 2nd Edition (HHS)",
    "source_pdfs/workouts/bulk_strength_conditioning_fundamentals.pdf":
        "Strength & Conditioning Fundamentals",
    "source_pdfs/workouts/cut_12_week_weight_loss_workout_plan.pdf":
        "12-Week Weight Loss Workout Plan",
}


def _friendly_label(chunk_id):
    if chunk_id.startswith("source_pdfs/"):
        base_id = chunk_id.split("#chunk")[0]
        return PDF_SOURCE_TITLES.get(base_id, base_id)
    return TXT_SOURCE_TITLES.get(chunk_id, chunk_id)


def _dedupe_sources(chunks):
    """Converts retrieved chunks into a clean, deduplicated citation list. All 10
    exercises/ chunks collapse into one combined line (they're always included as
    a group, not chosen for relevance, so citing each individually would just be
    noise) - everything else cites by its own friendly title, in first-seen order.
    """
    labels = []
    seen = set()
    has_exercise_chunk = False

    for chunk in chunks:
        if chunk["subdir"] == "exercises":
            has_exercise_chunk = True
            continue
        label = _friendly_label(chunk["id"])
        if label not in seen:
            seen.add(label)
            labels.append(label)

    if has_exercise_chunk:
        labels.insert(0, "App's Tracked Exercise Library (all 10 supported movements)")

    return labels

_model = None
_chunks = None
_embeddings = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model


def _load_chunks():
    chunks = []
    for path in sorted(glob.glob(os.path.join(KNOWLEDGE_DIR, "**", "*.txt"), recursive=True)):
        with open(path) as f:
            text = f.read().strip()
        if text:
            # subdir groups chunks by concern (exercises/splits/nutrition) so retrieval
            # can be scoped to just one concern instead of ranking across all of them -
            # ranking the full mixed corpus let unrelated goal/BMI chunks crowd out exercise
            # chunks that should always be included regardless of the user's goal.
            subdir = os.path.dirname(os.path.relpath(path, KNOWLEDGE_DIR))
            chunks.append({"id": os.path.relpath(path, KNOWLEDGE_DIR), "subdir": subdir, "goal_tag": None, "text": text})

    # PDF-derived chunks carry their own goal_tag (parsed from filename) used to filter
    # them before ranking - see retrieve_pdf_chunks below.
    chunks.extend(load_pdf_chunks())
    return chunks


def _build_or_load_index():
    global _chunks, _embeddings
    if _chunks is not None and _embeddings is not None:
        return

    chunks = _load_chunks()
    ids = [c["id"] for c in chunks]

    if os.path.exists(CACHE_PATH):
        cached = np.load(CACHE_PATH, allow_pickle=True)
        if list(cached["ids"]) == ids:
            _chunks = chunks
            _embeddings = cached["embeddings"]
            return

    model = _get_model()
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts, normalize_embeddings=True)
    np.savez(CACHE_PATH, ids=np.array(ids, dtype=object), embeddings=embeddings)
    _chunks = chunks
    _embeddings = embeddings


def retrieve(query, k=5, subdir=None):
    """Top-k knowledge_base chunks (full dicts, so callers can cite the source id)
    ranked by cosine similarity to `query`. If `subdir` is given (e.g. "splits",
    "nutrition"), only chunks under that knowledge_base subdirectory are ranked/returned.
    """
    _build_or_load_index()
    model = _get_model()
    query_vec = model.encode([query], normalize_embeddings=True)[0]

    candidate_idx = [i for i, c in enumerate(_chunks) if subdir is None or c["subdir"] == subdir]
    scores = _embeddings[candidate_idx] @ query_vec
    ranked = [candidate_idx[i] for i in np.argsort(scores)[::-1][:k]]
    return [_chunks[i] for i in ranked]


def retrieve_pdf_chunks(query, category, goal_tags, k=3):
    """Top-k PDF-derived chunks ranked by cosine similarity to `query`, filtered first
    to only chunks under source_pdfs/<category> whose document-level goal_tag is in
    `goal_tags`. The filter is deterministic (same reasoning as diet above - a document
    tagged BULK has no business appearing in a CUT plan no matter how it scores), and
    semantic ranking only decides which few paragraphs *within* that already-correct
    set are most relevant, rather than being asked to resolve the category itself.
    """
    _build_or_load_index()
    subdir = f"source_pdfs/{category}"
    model = _get_model()
    query_vec = model.encode([query], normalize_embeddings=True)[0]

    candidate_idx = [
        i for i, c in enumerate(_chunks)
        if c["subdir"] == subdir and c["goal_tag"] in goal_tags
    ]
    if not candidate_idx:
        return []
    scores = _embeddings[candidate_idx] @ query_vec
    ranked = [candidate_idx[i] for i in np.argsort(scores)[::-1][:k]]
    return [_chunks[i] for i in ranked]


def retrieve_by_id(chunk_id):
    """Exact lookup of one knowledge_base chunk by its relative path id, bypassing
    similarity ranking entirely - for fields that are already known exactly rather
    than needing to be inferred from a fuzzy query.
    """
    _build_or_load_index()
    for chunk in _chunks:
        if chunk["id"] == chunk_id:
            return [chunk]
    return []


def retrieve_plan_context(goal, bmi_category, diet_category):
    """Assembles the full retrieval-augmented context for one profile:
    - every exercise chunk (always relevant - the app can only track these 10 movements
      regardless of goal, so this is a deterministic scope rather than a similarity guess)
    - the goal-matching split strategy, semantically retrieved from splits/
    - the goal-matching nutrition strategy, semantically retrieved from nutrition/ goal docs
    - a BMI-context chunk, included only when BMI category makes the stated goal risky
    - the diet-matching protein/food-source strategy, semantically retrieved from diet/
    - a handful of supporting paragraphs pulled from the longer source PDFs, filtered to
      the user's goal (plus BMI/general docs where relevant) and ranked within that set
    """
    exercise_chunks = retrieve("bodyweight and dumbbell exercise", k=10, subdir="exercises")

    goal_query = f"training split and rep ranges for {GOAL_LABELS[goal]}"
    split_chunks = retrieve(goal_query, k=1, subdir="splits")

    nutrition_query = f"daily calorie and macro nutrition guidance for {GOAL_LABELS[goal]}"
    nutrition_chunks = retrieve(nutrition_query, k=1, subdir="nutrition")

    bmi_relevant = bmi_category in ("Underweight", "Overweight", "Obese")

    bmi_chunks = []
    if bmi_category == "Underweight":
        bmi_chunks = retrieve("underweight BMI nutrition caution", k=1, subdir="nutrition")
    elif bmi_category in ("Overweight", "Obese"):
        bmi_chunks = retrieve("overweight obese BMI nutrition caution", k=1, subdir="nutrition")

    diet_chunks = retrieve_by_id(DIET_FILES[diet_category])

    nutrition_goal_tags = [goal] + (["BMI"] if bmi_relevant else [])
    pdf_nutrition_chunks = retrieve_pdf_chunks(
        f"meal planning and nutrition advice for {GOAL_LABELS[goal]}",
        category="nutrition", goal_tags=nutrition_goal_tags, k=3,
    )

    workout_goal_tags = [goal, "GENERAL"]
    pdf_workout_chunks = retrieve_pdf_chunks(
        f"workout program structure and training advice for {GOAL_LABELS[goal]}",
        category="workouts", goal_tags=workout_goal_tags, k=3,
    )

    all_chunks = (
        exercise_chunks + split_chunks + nutrition_chunks + bmi_chunks + diet_chunks
        + pdf_nutrition_chunks + pdf_workout_chunks
    )

    context_texts = [c["text"] for c in all_chunks]
    sources = _dedupe_sources(all_chunks)
    return context_texts, sources
