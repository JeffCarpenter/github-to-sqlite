from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, List, Optional, cast

from nltk.tokenize import sent_tokenize

from .config import config

try:  # Optional dependencies
    from colorama import Fore, Style
except Exception:  # pragma: no cover - color output not essential
    class _Color(str, Enum):
        RED = ""
        GREEN = ""
        BLUE = ""
        MAGENTA = ""

    class _Style(Enum):
        RESET_ALL = ""

    Fore = _Color
    Style = _Style

if TYPE_CHECKING:
    from semantic_router.encoders.base import DenseEncoder
else:
    try:
        from semantic_router.encoders.base import DenseEncoder
    except Exception:  # pragma: no cover - optional dependency not installed
        @dataclass
        class DenseEncoder:
            """Fallback encoder used only for typing."""

            name: str = "default"


@dataclass(slots=True)
class Chunk:
    """A single chunk of text produced by the chunker."""

    content: str
    token_count: int
    is_triggered: bool
    triggered_score: float


@dataclass(slots=True)
class BaseSplitter:
    """Callable object that splits text into sentence strings."""

    def __call__(self, doc: str) -> List[str]:
        raise NotImplementedError("Subclasses must implement this method")


@dataclass
class BaseChunker:
    """Base class for chunkers."""

    name: str
    splitter: BaseSplitter
    encoder: Optional[DenseEncoder] = None

    def __post_init__(self) -> None:
        if self.encoder is None:
            self.encoder = DenseEncoder()

    def __call__(self, docs: List[str]) -> List[List[Chunk]]:
        raise NotImplementedError

    def _split(self, doc: str) -> List[str]:
        return self.splitter(doc)

    def _chunk(self, splits: List[Any]) -> List[Chunk]:
        raise NotImplementedError

    def print(self, document_splits: List[Chunk]) -> None:
        """Display chunks using color if ``colorama`` is installed."""

        if hasattr(Fore, "RED"):
            colors = [Fore.RED, Fore.GREEN, Fore.BLUE, Fore.MAGENTA]
            reset = getattr(Style, "RESET_ALL", "")
        else:
            colors = ["", "", "", ""]
            reset = ""
        for i, split in enumerate(document_splits):
            color = colors[i % len(colors)]
            colored_content = f"{color}{split.content}{reset}"
            if split.is_triggered:
                triggered = f"{split.triggered_score:.2f}"
            elif i == len(document_splits) - 1:
                triggered = "final split"
            else:
                triggered = "token limit"
            print(
                f"Split {i + 1}, tokens {split.token_count}, triggered by: {triggered}"
            )
            print(colored_content)
            print("-" * 88)
            print()


@dataclass
class SimpleChunker(BaseChunker):
    """Chunk text into groups of ``target_length`` sentences."""

    target_length: int = field(default=config.max_length)

    def __call__(self, docs: List[str]) -> List[List[Chunk]]:
        return [self._chunk(self._split(doc)) for doc in docs]

    def _split(self, doc: str) -> List[str]:
        try:
            return cast(List[str], sent_tokenize(doc))
        except LookupError:  # pragma: no cover - depends on environment
            import nltk

            class PunktResource(str, Enum):
                PUNKT = "punkt"
                PUNKT_TAB = "punkt_tab"

            for resource in PunktResource:
                nltk.download(resource.value)
                try:
                    return cast(List[str], sent_tokenize(doc))
                except LookupError:
                    continue
            raise

    def _chunk(self, sentences: List[str]) -> List[Chunk]:
        chunks: List[Chunk] = []
        for i in range(0, len(sentences), self.target_length):
            piece = sentences[i : i + self.target_length]
            # Include final chunk even if shorter than target_length
            if not piece:
                break
            content = " ".join(piece)
            chunks.append(
                Chunk(
                    content=content,
                    token_count=len(piece),
                    is_triggered=False,
                    triggered_score=0.0,
                )
            )
        return chunks

