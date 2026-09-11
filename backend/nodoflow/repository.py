import hashlib
import json
import uuid
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

def new_id():
    return str(uuid.uuid4())

class IdempotencyConflict(Exception):
    pass

async def add_outbox(conn, route, payload):
    message_id = new_id()
    body = {"schema_version": 1, "message_id": message_id, **payload}
    await conn.execute(text(
        "INSERT INTO outbox(message_id,route,payload) VALUES (:id,:route,CAST(:payload AS jsonb))"
    ), {"id": message_id, "route": route, "payload": json.dumps(body)})

class TaskRepository:
    def __init__(self, engine):
        self.engine = engine

    async def submit(self, request):
        body = {"type": request.type, "payload": request.payload.model_dump()}
        fingerprint = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        task_id = new_id()
        try:
            async with self.engine.begin() as conn:
                await conn.execute(text("""
                    INSERT INTO tasks(task_id,task_type,payload,idempotency_key,fingerprint,state)
                    VALUES (:id,:type,CAST(:payload AS jsonb),:key,:fingerprint,'PENDING')
                """), {"id": task_id, "type": request.type, "payload": json.dumps(body["payload"]),
                       "key": request.idempotency_key, "fingerprint": fingerprint})
                await add_outbox(conn, "nf.ready", {"event": "TaskAccepted", "task_id": task_id,
                                                   "correlation_id": task_id})
        except IntegrityError:
            if not request.idempotency_key:
                raise
            async with self.engine.connect() as conn:
                row = (await conn.execute(text(
                    "SELECT task_id,fingerprint FROM tasks WHERE idempotency_key=:key"
                ), {"key": request.idempotency_key})).mappings().first()
            if not row:
                raise
            if row["fingerprint"] != fingerprint:
                raise IdempotencyConflict()
            task_id = row["task_id"]
        return await self.get(task_id)

    async def get(self, task_id):
        async with self.engine.connect() as conn:
            row = (await conn.execute(text("SELECT * FROM tasks WHERE task_id=:id"),
                                      {"id": task_id})).mappings().first()
            if not row:
                return None
            attempts = (await conn.execute(text(
                "SELECT * FROM attempts WHERE task_id=:id ORDER BY created_at"
            ), {"id": task_id})).mappings().all()
            result = dict(row)
            result.pop("fingerprint")
            result["attempts"] = [dict(a) for a in attempts]
            return result

    async def list(self, state=None):
        async with self.engine.connect() as conn:
            ids = (await conn.execute(text(
                "SELECT task_id FROM tasks " +
                ("WHERE state=:state " if state else "") +
                "ORDER BY created_at DESC LIMIT 100"
            ), {"state": state} if state else {})).scalars().all()
        return [await self.get(task_id) for task_id in ids]

    async def register(self, node):
        async with self.engine.begin() as conn:
            await conn.execute(text("""
                INSERT INTO nodes(node_id,capacity) VALUES (:id,:capacity)
                ON CONFLICT (node_id) DO UPDATE SET capacity=:capacity,heartbeat_at=now()
            """), {"id": node.node_id, "capacity": node.capacity})

    async def nodes(self, liveness):
        async with self.engine.connect() as conn:
            return [dict(row) for row in (await conn.execute(text("""
                SELECT n.*, (heartbeat_at > now() - :seconds * interval '1 second') AS available,
                  (SELECT count(*) FROM attempts a WHERE a.node_id=n.node_id
                    AND a.state IN ('ASSIGNED','RUNNING')) AS busy
                FROM nodes n ORDER BY node_id
            """), {"seconds": liveness})).mappings().all()]

    async def assign_one(self, liveness):
        async with self.engine.begin() as conn:
            # Serialize scheduling decisions without sharing node memory.
            await conn.execute(text("SELECT pg_advisory_xact_lock(60402)"))
            task = (await conn.execute(text("""
                SELECT * FROM tasks WHERE state='PENDING' ORDER BY created_at
                LIMIT 1 FOR UPDATE SKIP LOCKED
            """))).mappings().first()
            if not task:
                return False
            node = (await conn.execute(text("""
                SELECT n.node_id FROM nodes n
                WHERE heartbeat_at > now() - :seconds * interval '1 second'
                AND (SELECT count(*) FROM attempts a WHERE a.node_id=n.node_id
                     AND a.state IN ('ASSIGNED','RUNNING')) < n.capacity
                ORDER BY (SELECT count(*) FROM attempts a WHERE a.node_id=n.node_id
                          AND a.state IN ('ASSIGNED','RUNNING')), n.node_id
                LIMIT 1 FOR UPDATE
            """), {"seconds": liveness})).mappings().first()
            if not node:
                return False
            attempt_id = new_id()
            await conn.execute(text("""
                INSERT INTO attempts(attempt_id,task_id,node_id,state)
                VALUES (:attempt,:task,:node,'ASSIGNED')
            """), {"attempt": attempt_id, "task": task["task_id"], "node": node["node_id"]})
            await conn.execute(text(
                "UPDATE tasks SET state='RUNNING',updated_at=now() WHERE task_id=:id"
            ), {"id": task["task_id"]})
            await add_outbox(conn, "nf.work." + node["node_id"], {
                "event": "ExecuteTask", "task_id": task["task_id"], "attempt_id": attempt_id,
                "node_id": node["node_id"], "correlation_id": task["task_id"],
                "payload": task["payload"],
            })
            return True

    async def report(self, event):
        async with self.engine.begin() as conn:
            task = (await conn.execute(text(
                "SELECT state FROM tasks WHERE task_id=:id FOR UPDATE"
            ), {"id": event["task_id"]})).mappings().first()
            attempt = (await conn.execute(text("""
                SELECT state FROM attempts WHERE attempt_id=:attempt
                AND task_id=:task AND node_id=:node FOR UPDATE
            """), {"attempt": event["attempt_id"], "task": event["task_id"],
                   "node": event["node_id"]})).mappings().first()
            if not task or not attempt or task["state"] in ("SUCCEEDED","FAILED"):
                return False
            if attempt["state"] not in ("ASSIGNED","RUNNING"):
                return False
            if event["event"] == "AttemptStarted":
                await conn.execute(text("""
                    UPDATE attempts SET state='RUNNING',started_at=COALESCE(started_at,now())
                    WHERE attempt_id=:id
                """), {"id": event["attempt_id"]})
                return True
            if event["event"] not in ("AttemptSucceeded", "AttemptFailed"):
                return False
            state = "SUCCEEDED" if event["event"] == "AttemptSucceeded" else "FAILED"
            await conn.execute(text("""
                UPDATE attempts SET state=:state,worker_id=:worker,
                started_at=COALESCE(started_at,now()),finished_at=now() WHERE attempt_id=:id
            """), {"state": state, "worker": event.get("worker_id"), "id": event["attempt_id"]})
            await conn.execute(text("""
                UPDATE tasks SET state=:state,result=CAST(:result AS jsonb),error=:error,
                updated_at=now() WHERE task_id=:id
            """), {"state": state, "result": json.dumps(event.get("result")),
                   "error": event.get("error"), "id": event["task_id"]})
            return True
