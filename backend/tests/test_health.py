from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from nodoflow.app import create_app
from nodoflow.settings import Settings

def test_node_has_no_database_access():
    with pytest.raises(ValidationError, match="database credentials"):
        Settings(role="node", node_id="A", amqp_url="amqp://unused",
                 database_url="postgresql+psycopg://unused")

def test_liveness_survives_missing_dependencies(monkeypatch):
    async def unavailable(*args, **kwargs):
        raise OSError("secret-that-must-not-leak")
    monkeypatch.setattr("nodoflow.app.aio_pika.connect", unavailable)
    settings = Settings(role="node", node_id="A", amqp_url="amqp://unused",
                        application_url="http://127.0.0.1:1", io_timeout_seconds=0.1)
    with TestClient(create_app(settings, start_runtime=False)) as client:
        assert client.get("/health/live").status_code == 200
        result = client.get("/health/ready")
        assert result.status_code == 503
        assert result.json()["dependencies"]["rabbitmq"] is False
        assert "secret-that-must-not-leak" not in result.text
        assert result.json()["task_processing_enabled"] is False
