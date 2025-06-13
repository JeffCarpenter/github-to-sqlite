from pydantic import BaseModel


class Config(BaseModel):
    default_model: str = "Alibaba-NLP/gte-modernbert-base"
    onnx_provider: str = "cpu"
    max_length: int = 8192


config = Config()
