"""Run inside the application container; leaves named verification tasks for traceability."""
import asyncio
import uuid
import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from nodoflow.settings import Settings
from nodoflow.repository import TaskRepository

async def verify():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=5) as client:
        invalid = await client.post("/tasks", json={"payload":{"value":"","duration_ms":-1}})
        assert invalid.status_code == 422
        unsupported = await client.post("/tasks", json={"type":"execute_code","payload":{"value":"test"}})
        assert unsupported.status_code == 422
        body = {"payload":{"value":"verificación de flujo","duration_ms":500},
                "idempotency_key":"verify-" + str(uuid.uuid4())}
        responses = await asyncio.gather(*(client.post("/tasks", json=body) for _ in range(4)))
        assert all(r.status_code == 202 for r in responses)
        ids = {r.json()["task_id"] for r in responses}
        assert len(ids) == 1, "Concurrent idempotency created multiple tasks"
        task_id = ids.pop()
        conflict = await client.post("/tasks", json={**body,"payload":{"value":"different","duration_ms":500}})
        assert conflict.status_code == 409
        for _ in range(60):
            task = (await client.get("/tasks/" + task_id)).json()
            if task["state"] in ("SUCCEEDED","FAILED"):
                break
            await asyncio.sleep(.25)
        assert task["state"] == "SUCCEEDED", task
        assert task["result"]["value"] == "VERIFICACIÓN DE FLUJO"
        assert len(task["attempts"]) == 1
        assert task["attempts"][0]["node_id"] == "A"
        assert task["attempts"][0]["worker_id"].startswith("node-A")
        settings = Settings()
        engine = create_async_engine(settings.database_url.get_secret_value())
        repo = TaskRepository(engine)
        duplicate = {"event":"AttemptSucceeded", "task_id":task_id,
                     "attempt_id":task["attempts"][0]["attempt_id"], "node_id":"A",
                     "result":{"value":"WRONG"}}
        assert await repo.report(duplicate) is False
        assert await repo.report({**duplicate,"event":"AttemptStarted"}) is False
        assert (await repo.get(task_id))["result"] == task["result"]
        async with engine.connect() as conn:
            outbox = (await conn.execute(text("""
                SELECT count(*) FROM outbox
                WHERE payload->>'task_id'=:id AND published_at IS NOT NULL
            """), {"id":task_id})).scalar_one()
        assert outbox == 2, "Acceptance and assignment must be durable and published"
        await engine.dispose()
        missing = await client.get("/tasks/" + str(uuid.uuid4()))
        assert missing.status_code == 404
        print("PASS: validation, concurrent idempotency, conflict, durable outbox, real node execution, terminal protection, 404")
        print("Verification task:", task_id)
asyncio.run(verify())
