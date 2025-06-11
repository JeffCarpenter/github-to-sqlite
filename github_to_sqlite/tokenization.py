from dataclasses import dataclass
from functools import partial
from tokenizers import Tokenizer

from .config import config


@dataclass(frozen=True, slots=True)
class Token:
    id: int
    value: str
    offsets: tuple[int, int]


load_tokenizer = partial(Tokenizer.from_pretrained, config.default_model)
