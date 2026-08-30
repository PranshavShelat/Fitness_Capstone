import glob
import os
import re

from pypdf import PdfReader

PDF_SOURCE_DIR = "knowledge_base/source_pdfs"
CHUNK_WORDS = 200
MIN_CHUNK_WORDS = 40
MAX_CHUNKS_PER_DOC = 40

# Filenames are prefixed by convention (cut_/maintain_/bulk_/bmi_/general_) - this
# parses that prefix into the tag used to filter which PDF a query is even allowed
# to draw from, so a CUT plan never surfaces paragraphs from the BULK nutrition PDF.
def _goal_tag_from_filename(filename):
    prefix = filename.split("_")[0].upper()
    return prefix if prefix in ("CUT", "MAINTAIN", "BULK", "BMI", "GENERAL") else "GENERAL"


def _extract_text(path):
    reader = PdfReader(path)
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n\n".join(pages)


def _is_low_quality(chunk):
    words = chunk.split()
    if len(words) < MIN_CHUNK_WORDS:
        return True
    alpha_chars = sum(1 for c in chunk if c.isalpha())
    return alpha_chars < len(chunk) * 0.5


def _chunk_text(text):
    """Groups paragraphs into ~CHUNK_WORDS-sized chunks (never splitting a paragraph
    across chunks unless it's alone and longer than that), then drops chunks that are
    too short or too non-alphabetic to be page numbers/headers/table fragments rather
    than real prose.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    chunks = []
    current = []
    current_words = 0
    for para in paragraphs:
        para_words = len(para.split())
        if current and current_words + para_words > CHUNK_WORDS:
            chunks.append(" ".join(current))
            current, current_words = [], 0
        current.append(para)
        current_words += para_words
    if current:
        chunks.append(" ".join(current))

    return [c for c in chunks if not _is_low_quality(c)]


def _subsample(chunks, limit):
    """Caps chunk count per document so one long PDF (e.g. a 400-page field manual)
    can't dominate a retrieval pool purely by chunk volume over a short one - takes
    an even spread across the document rather than just the first N chunks, so both
    the start and end of the source are still represented.
    """
    if len(chunks) <= limit:
        return chunks
    step = len(chunks) / limit
    return [chunks[int(i * step)] for i in range(limit)]


def load_pdf_chunks():
    """Extracts, chunks, and tags every PDF under knowledge_base/source_pdfs/.
    Returns a list of {id, subdir, goal_tag, text} dicts in the same shape rag.py
    uses for its .txt chunks, so both can be embedded and searched together.
    """
    chunks = []
    for path in sorted(glob.glob(os.path.join(PDF_SOURCE_DIR, "**", "*.pdf"), recursive=True)):
        rel_path = os.path.relpath(path, "knowledge_base")
        category = os.path.basename(os.path.dirname(path))  # "nutrition" or "workouts"
        filename = os.path.basename(path)
        goal_tag = _goal_tag_from_filename(filename)

        text = _extract_text(path)
        doc_chunks = _subsample(_chunk_text(text), MAX_CHUNKS_PER_DOC)

        for i, chunk_text in enumerate(doc_chunks):
            chunks.append({
                "id": f"{rel_path}#chunk{i}",
                "subdir": os.path.dirname(rel_path),  # "source_pdfs/nutrition" or "source_pdfs/workouts"
                "category": category,
                "goal_tag": goal_tag,
                "text": chunk_text,
            })

    return chunks
