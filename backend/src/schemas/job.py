from pydantic import BaseModel, Field
class JobInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    dataset_id: int
    params: dict = Field(default_factory=dict)
    # 可显式指定版本；为空时接单瞬间解析当前默认版本并钉在任务上
    engine_version: str | None = Field(default=None, max_length=20)
