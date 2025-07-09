from pydantic import BaseModel


class Config(BaseModel):
    default_model: str = "Alibaba-NLP/gte-modernbert-base"
    onnx_provider: str = "cpu"
    max_length: int = 8192
    embedding_dim: int = 768
    build_patterns: list[str] = [
        "pyproject.toml",
        "package.json",
        "Cargo.toml",
        "Gemfile",
    ]


config = Config()
