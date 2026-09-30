"""One place for how this app talks to Gemini.

Why: the report, the workout/meal planner and the coach chat each called Gemini
directly, so each one broke separately whenever Google's servers were overloaded
(503) - the report had retry logic, the planner did not. Now all three share:

  * the model names (change them HERE, nowhere else),
  * retrying on 503 (model overloaded) / 429 (rate limited), which are usually
    over within seconds,
  * falling back to a lighter backup model if the main one stays busy.

Errors that retrying cannot fix (bad API key, bad model name) are raised at once.
"""
import os
import time

from google import genai

GEMINI_MODEL = "gemini-3.5-flash"
# Tried when GEMINI_MODEL keeps answering 503/429 - a lighter model is usually
# less crowded, and an answer from it beats no answer.
GEMINI_BACKUP_MODEL = "gemini-3.5-flash-lite"

_TRANSIENT = ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED")


def is_transient(error):
    return any(code in str(error) for code in _TRANSIENT)


def get_client(purpose="this feature"):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(f"GEMINI_API_KEY is not set - add it to a .env file before using {purpose}.")
    return genai.Client(api_key=api_key)


def generate(prompt, json_output=False, purpose="this feature"):
    """generate_content with retries and the backup model. Returns response.text."""
    client = get_client(purpose)
    # AFC (automatic function calling) is off because no tools are used here -
    # left on, it only printed a warning on every call.
    config = {"automatic_function_calling": {"disable": True}}
    if json_output:
        # The API itself guarantees valid JSON, instead of trusting the model to
        # follow a formatting instruction.
        config["response_mime_type"] = "application/json"

    # Main model: 3 tries (waiting 2 s, then 5 s). Backup model: 2 tries.
    attempts = [(GEMINI_MODEL, 0), (GEMINI_MODEL, 2), (GEMINI_MODEL, 5),
                (GEMINI_BACKUP_MODEL, 0), (GEMINI_BACKUP_MODEL, 3)]
    response = None
    for i, (model, wait) in enumerate(attempts):
        if wait:
            time.sleep(wait)
        try:
            response = client.models.generate_content(model=model, contents=prompt, config=config)
            if model != GEMINI_MODEL:
                print(f"Gemini ({purpose}): {GEMINI_MODEL} was busy, used backup model {model}")
            break
        except Exception as e:
            if not is_transient(e) or i == len(attempts) - 1:
                raise
            nxt_model, nxt_wait = attempts[i + 1]
            print(f"Gemini ({purpose}) {model} busy ({str(e)[:40]}...), trying {nxt_model} in {nxt_wait}s")

    if not response.text:
        reason = (getattr(response.candidates[0], "finish_reason", "?")
                  if response.candidates else "no candidates")
        raise RuntimeError(f"Gemini returned an empty response (finish reason: {reason})")
    return response.text


def retry_transient(fn, purpose="this feature", waits=(2, 5)):
    """Call fn(), retrying on 503/429. For calls that can't switch model midway,
    like sending a message in an existing chat session."""
    for i in range(len(waits) + 1):
        try:
            return fn()
        except Exception as e:
            if not is_transient(e) or i == len(waits):
                raise
            print(f"Gemini ({purpose}) busy ({str(e)[:40]}...), retrying in {waits[i]}s")
            time.sleep(waits[i])
