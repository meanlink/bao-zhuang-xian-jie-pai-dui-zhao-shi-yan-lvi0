from pydantic import BaseModel, Field


class ReleaseInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    candidate_version: str = Field(min_length=1, max_length=20)
    dataset_ids: list[int] = Field(min_length=1)
    params_list: list[dict] | None = None
    tolerance: dict | None = None
    validity_hours: int = Field(default=168, ge=1, le=720)


class RetireVersionInput(BaseModel):
    version: str = Field(min_length=1, max_length=20)
