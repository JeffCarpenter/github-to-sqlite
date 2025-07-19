from dataclasses import dataclass
import os
from tokenizers import Tokenizer

from .config import config


@dataclass(frozen=True, slots=True)
class Token:
    id: int
    value: str
    offsets: tuple[int, int]



def load_tokenizer(model: str | None = None) -> Tokenizer:
    """Load a Hugging Face tokenizer.

    Uses the provided model name or the ``GITHUB_TO_SQLITE_MODEL`` environment
    variable, falling back to :data:`config.default_model`.
    """
    model_name = model or os.environ.get("GITHUB_TO_SQLITE_MODEL", config.default_model)
    try:
        return Tokenizer.from_pretrained(model_name)
    except Exception as e:  # pragma: no cover - exercised in tests
        raise RuntimeError(
            f"Failed to load tokenizer for model '{model_name}': {e}"
        ) from e
