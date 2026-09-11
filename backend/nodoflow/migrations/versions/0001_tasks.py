from alembic import op
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""
        CREATE TABLE nodes (
            node_id TEXT PRIMARY KEY, capacity INTEGER NOT NULL CHECK (capacity > 0),
            heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE tasks (
            task_id TEXT PRIMARY KEY, task_type TEXT NOT NULL,
            payload JSONB NOT NULL, idempotency_key TEXT UNIQUE,
            fingerprint TEXT NOT NULL,
            state TEXT NOT NULL CHECK (state IN ('PENDING','RUNNING','RETRY_PENDING','SUCCEEDED','FAILED')),
            result JSONB, error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE attempts (
            attempt_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id),
            node_id TEXT NOT NULL REFERENCES nodes(node_id),
            state TEXT NOT NULL CHECK (state IN ('ASSIGNED','RUNNING','SUCCEEDED','FAILED','ABANDONED')),
            worker_id TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ
        );
        CREATE UNIQUE INDEX one_active_attempt ON attempts(task_id)
            WHERE state IN ('ASSIGNED','RUNNING');
        CREATE INDEX task_order ON tasks(state, created_at);
        CREATE TABLE outbox (
            message_id TEXT PRIMARY KEY, route TEXT NOT NULL, payload JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(), published_at TIMESTAMPTZ
        );
        CREATE INDEX outbox_pending ON outbox(created_at) WHERE published_at IS NULL;
    """)

def downgrade():
    raise RuntimeError("Destructive downgrade requires a separately reviewed migration")
