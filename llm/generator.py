"""Generation lewat Ollama (local LLM, GPU VRAM)."""
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ollama

from common.settings import OLLAMA_HOST, OLLAMA_MODEL
from llm.prompts import SYSTEM_PROMPT, build_user_prompt

_client: Optional[ollama.Client] = None


def _get_client() -> ollama.Client:
    global _client
    if _client is None:
        _client = ollama.Client(host=OLLAMA_HOST)
    return _client


def generate_answer(query: str, context_block: str, model: str = OLLAMA_MODEL) -> str:
    client = _get_client()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(query, context_block)},
    ]
    response = client.chat(model=model, messages=messages)
    return response["message"]["content"]
