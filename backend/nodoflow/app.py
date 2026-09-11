import asyncio
import json
import logging
from contextlib import asynccontextmanager
from urllib.request import urlopen

import aio_pika
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from prometheus_client import CollectorRegistry, Gauge, CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from .settings import Settings
from .repository import TaskRepository
from .runtime import migrate, application_runtime, node_runtime
from .api import router

logger = logging.getLogger("nodoflow")

class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({"level": record.levelname, "event": record.getMessage()}, ensure_ascii=False)

def create_app(settings: Settings | None = None, start_runtime: bool = True) -> FastAPI:
    settings = settings or Settings()
    registry = CollectorRegistry()
    info = Gauge("nodoflow_service_info", "Service identity; not functional task readiness",
                 ["role", "node_id"], registry=registry)
    readiness = Gauge("nodoflow_dependency_ready", "Last dependency readiness probe",
                      ["dependency"], registry=registry)

    @asynccontextmanager
    async def lifespan(app):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        app.state.engine = (
            create_async_engine(settings.database_url.get_secret_value(), pool_pre_ping=True,
                                connect_args={"connect_timeout": 2})
            if settings.database_url else None
        )
        info.labels(settings.role, settings.node_id or "control").set(1)
        app.state.settings = settings
        app.state.runtime_connected = False
        background = None
        if start_runtime:
            if settings.role == "application":
                await asyncio.to_thread(migrate, settings)
                app.state.repository = TaskRepository(app.state.engine)
                background = asyncio.create_task(application_runtime(app, settings))
            else:
                background = asyncio.create_task(node_runtime(app, settings))
        logger.info("service_started")
        try:
            yield
        finally:
            if background:
                background.cancel()
                await asyncio.gather(background, return_exceptions=True)
            if app.state.engine is not None:
                await app.state.engine.dispose()
            logger.info("service_stopped")
            logger.removeHandler(handler)
            handler.close()

    app = FastAPI(title="NodoFlow", version="0.2.0", lifespan=lifespan)
    if settings.role == "application":
        app.include_router(router)

    async def postgres_probe():
        async with app.state.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def rabbitmq_probe():
        connection = await aio_pika.connect(settings.amqp_url.get_secret_value(),
                                            timeout=settings.io_timeout_seconds)
        try:
            channel = await connection.channel()
            await channel.close()
        finally:
            await connection.close()

    async def application_probe():
        def request():
            with urlopen(settings.application_url + "/health/live",
                         timeout=settings.io_timeout_seconds) as response:
                if response.status != 200:
                    raise RuntimeError("Application unavailable")
        await asyncio.to_thread(request)

    @app.get("/health/live")
    async def live():
        return {"status": "alive", "role": settings.role, "node_id": settings.node_id}

    @app.get("/health/ready")
    async def ready():
        probes = {"rabbitmq": rabbitmq_probe}
        if settings.role == "application":
            probes["postgresql"] = postgres_probe
        else:
            probes["application"] = application_probe

        async def check(name, probe):
            try:
                await asyncio.wait_for(probe(), timeout=settings.io_timeout_seconds)
                value = True
            except Exception:
                # Do not expose connection strings or provider exception details.
                value = False
            readiness.labels(name).set(int(value))
            return name, value

        dependencies = dict(await asyncio.gather(*(check(k, v) for k, v in probes.items())))
        ok = all(dependencies.values())
        return JSONResponse(
            {"status": "ready" if ok else "not_ready", "role": settings.role,
             "node_id": settings.node_id, "dependencies": dependencies,
             "stage": "task-flow", "task_processing_enabled": app.state.runtime_connected},
            status_code=200 if ok else 503,
        )

    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    return app
