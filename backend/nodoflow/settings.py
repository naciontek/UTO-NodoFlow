from typing import Literal
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NF_", extra="ignore")
    role: Literal["application", "node"] = "application"
    node_id: str | None = None
    database_url: SecretStr | None = None
    amqp_url: SecretStr
    application_url: str = "http://application:8000"
    workers_per_node: int = Field(default=4, ge=1, le=64)
    heartbeat_seconds: float = Field(default=2, gt=0)
    liveness_seconds: float = Field(default=6, gt=0)
    liveness_scan_seconds: float = Field(default=1, gt=0)
    io_timeout_seconds: float = Field(default=2, gt=0, le=30)
    max_attempts: int = Field(default=3, ge=1)

    @model_validator(mode="after")
    def validate_role(self):
        if self.role == "application" and self.database_url is None:
            raise ValueError("Application requires NF_DATABASE_URL")
        if self.role == "node" and not self.node_id:
            raise ValueError("Node requires NF_NODE_ID")
        if self.role == "node" and self.database_url is not None:
            raise ValueError("Nodes must not receive database credentials")
        if self.liveness_seconds <= self.heartbeat_seconds:
            raise ValueError("Liveness must exceed heartbeat interval")
        return self
