from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str = Field(min_length=1, max_length=500)
    duration_ms: int = Field(default=1000, ge=100, le=10000)
    failure_mode: Literal["none"] = "none"

class SubmitTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["controlled_delay_transform"] = "controlled_delay_transform"
    payload: Payload
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)

class NodeRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    node_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    capacity: int = Field(ge=1, le=64)
