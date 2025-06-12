from typing import Any, List, Optional
from dataclasses import dataclass

from .config import config

try:
    from pydantic.v1 import BaseModel, Extra, validator
    from colorama import Fore, Style
    from semantic_router.encoders.base import DenseEncoder
except Exception:  # pragma: no cover - optional dependency not installed

    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    DenseEncoder = object  # type: ignore
    Fore = Style = None  # type: ignore

    class DummyExtra:
        allow = None
    Extra = DummyExtra  # type: ignore

    def validator(*args, **kwargs):
        def decorator(fn):
            return fn
        return decorator

@dataclass
class Chunk:
    content: str
    token_count: int
    is_triggered: bool
    triggered_score: float


@dataclass
class BaseSplitter:
    def __call__(self, doc: str) -> List[str]:
        raise NotImplementedError("Subclasses must implement this method")


class BaseChunker(BaseModel):
    name: str
    encoder: Optional[DenseEncoder]
    splitter: BaseSplitter

    class Config:
        extra = Extra.allow
        arbitrary_types_allowed = True

    @validator("encoder", pre=True, always=True)
    def set_encoder(cls, v):  # type: ignore
        if v is None:
            return DenseEncoder(name="default")
        return v

    def __call__(self, docs: List[str]) -> List[List[Chunk]]:
        raise NotImplementedError

    def _split(self, doc: str) -> List[str]:
        return self.splitter(doc)  # type: ignore

    def _chunk(self, splits: List[Any]) -> List[Chunk]:
        raise NotImplementedError

    def print(self, document_splits: List[Chunk]) -> None:
        colors = [Fore.RED, Fore.GREEN, Fore.BLUE, Fore.MAGENTA]
        for i, split in enumerate(document_splits):
            color = colors[i % len(colors)]
            colored_content = f"{color}{split.content}{Style.RESET_ALL}"
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
            print("\n")


from nltk.tokenize import sent_tokenize


class SimpleChunker(BaseChunker):
    """Chunk text into groups of ``target_length`` sentences."""

    target_length: int = config.max_length

    def __init__(self, name: str, splitter, encoder=None, target_length: int = config.max_length):
        try:
            super().__init__(name=name, splitter=splitter, encoder=encoder)
        except Exception:
            self.name = name
            self.splitter = splitter
            self.encoder = encoder
        self.target_length = target_length

    def __call__(self, docs: List[str]) -> List[List[Chunk]]:
        return [self._chunk(self._split(doc)) for doc in docs]

    def _split(self, doc: str) -> List[str]:
        try:
            return sent_tokenize(doc)
        except LookupError:  # pragma: no cover - depends on environment
            import nltk

            for resource in ("punkt", "punkt_tab"):
                nltk.download(resource)
                try:
                    return sent_tokenize(doc)
                except LookupError:
                    continue
            raise

    def _chunk(self, sentences: List[str]) -> List[Chunk]:
        chunks: List[Chunk] = []
        for i in range(0, len(sentences), self.target_length):
            piece = sentences[i : i + self.target_length]
            if len(piece) < self.target_length:
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

