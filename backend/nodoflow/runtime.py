import asyncio
import json
import logging
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import aio_pika
import httpx
from alembic import command
from alembic.config import Config
from sqlalchemy import text

logger = logging.getLogger("nodoflow")

def migrate(settings):
    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    cfg.attributes["url"] = settings.database_url.get_secret_value()
    command.upgrade(cfg, "head")

def transform(payload):
    # Deliberate I/O-like workload; never execute input as code.
    time.sleep(payload["duration_ms"] / 1000)
    return {"value": payload["value"].upper(), "characters": len(payload["value"])}, threading.current_thread().name

async def publish(channel, route, event, timeout):
    await channel.declare_queue(route, durable=True)
    await channel.default_exchange.publish(
        aio_pika.Message(body=json.dumps(event).encode(), content_type="application/json",
                         message_id=event.get("message_id", event.get("attempt_id")),
                         delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
        routing_key=route, mandatory=True, timeout=timeout,
    )

async def application_runtime(app, settings):
    repository = app.state.repository
    while True:
        connection = None
        jobs = []
        try:
            connection = await aio_pika.connect_robust(
                settings.amqp_url.get_secret_value(), timeout=settings.io_timeout_seconds)
            channel = await connection.channel(publisher_confirms=True)
            await channel.set_qos(prefetch_count=16)
            reports = await channel.declare_queue("nf.reports", durable=True)
            signals = await channel.declare_queue("nf.ready", durable=True)

            async def consume_signal(message):
                async with message.process(requeue=True):
                    # Task already durable; scheduling also reconciles PENDING tasks.
                    json.loads(message.body)

            async def consume_report(message):
                async with message.process(requeue=True):
                    event = json.loads(message.body)
                    accepted = await repository.report(event)
                    logger.info(json.dumps({"event": event["event"], "accepted": accepted,
                                            "task_id": event["task_id"], "attempt_id": event["attempt_id"],
                                            "node_id": event["node_id"]}))

            await signals.consume(consume_signal)
            await reports.consume(consume_report)

            async def dispatch():
                while True:
                    try:
                        async with repository.engine.begin() as conn:
                            rows = (await conn.execute(text("""
                                SELECT * FROM outbox WHERE published_at IS NULL
                                ORDER BY created_at LIMIT 20 FOR UPDATE SKIP LOCKED
                            """))).mappings().all()
                            for row in rows:
                                await publish(channel, row["route"], row["payload"], settings.io_timeout_seconds)
                                await conn.execute(text(
                                    "UPDATE outbox SET published_at=now() WHERE message_id=:id"
                                ), {"id": row["message_id"]})
                    except Exception as error:
                        logger.warning("outbox_retry:" + type(error).__name__)
                    await asyncio.sleep(0.2)

            async def schedule():
                while True:
                    try:
                        for _ in range(64):
                            if not await repository.assign_one(settings.liveness_seconds):
                                break
                    except Exception as error:
                        logger.warning("scheduler_retry:" + type(error).__name__)
                    await asyncio.sleep(0.2)

            app.state.runtime_connected = True
            jobs = [asyncio.create_task(dispatch()), asyncio.create_task(schedule())]
            await asyncio.gather(*jobs)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.warning("application_runtime_retry:" + type(error).__name__)
            await asyncio.sleep(1)
        finally:
            app.state.runtime_connected = False
            for job in jobs:
                job.cancel()
            await asyncio.gather(*jobs, return_exceptions=True)
            if connection:
                await connection.close()

async def node_runtime(app, settings):
    pool = ThreadPoolExecutor(max_workers=settings.workers_per_node,
                              thread_name_prefix="node-" + settings.node_id)
    semaphore = asyncio.Semaphore(settings.workers_per_node)
    cache = OrderedDict()
    locks = {}
    try:
        while True:
            connection = None
            heartbeat_job = None
            try:
                connection = await aio_pika.connect_robust(
                    settings.amqp_url.get_secret_value(), timeout=settings.io_timeout_seconds)
                channel = await connection.channel(publisher_confirms=True)
                await channel.set_qos(prefetch_count=settings.workers_per_node)
                queue = await channel.declare_queue("nf.work." + settings.node_id, durable=True)
                await channel.declare_queue("nf.reports", durable=True)

                async def execute(message):
                    async with message.process(requeue=True):
                        event = json.loads(message.body)
                        if event["node_id"] != settings.node_id:
                            raise ValueError("Misdirected assignment")
                        attempt = event["attempt_id"]
                        async with semaphore:
                            lock = locks.setdefault(attempt, asyncio.Lock())
                            async with lock:
                                if attempt not in cache:
                                    base = {"schema_version": 1, "task_id": event["task_id"],
                                            "attempt_id": attempt, "node_id": settings.node_id,
                                            "correlation_id": event["task_id"]}
                                    await publish(channel, "nf.reports",
                                                  {**base, "event": "AttemptStarted"},
                                                  settings.io_timeout_seconds)
                                    try:
                                        result, worker = await asyncio.get_running_loop().run_in_executor(
                                            pool, transform, event["payload"])
                                        terminal = {**base, "event": "AttemptSucceeded",
                                                    "result": result, "worker_id": worker}
                                    except Exception as error:
                                        terminal = {**base, "event": "AttemptFailed",
                                                    "error": type(error).__name__}
                                    cache[attempt] = terminal
                                await publish(channel, "nf.reports", cache[attempt], settings.io_timeout_seconds)
                                cache.move_to_end(attempt)
                                while len(cache) > 1000:
                                    cache.popitem(last=False)
                            locks.pop(attempt, None)

                await queue.consume(execute)
                async with httpx.AsyncClient(timeout=settings.io_timeout_seconds) as client:
                    async def heartbeat():
                        while True:
                            try:
                                response = await client.post(
                                    settings.application_url + "/internal/nodes/heartbeat",
                                    json={"node_id": settings.node_id, "capacity": settings.workers_per_node})
                                response.raise_for_status()
                                app.state.runtime_connected = True
                            except Exception as error:
                                app.state.runtime_connected = False
                                logger.warning("heartbeat_retry:" + type(error).__name__)
                            await asyncio.sleep(settings.heartbeat_seconds)
                    heartbeat_job = asyncio.create_task(heartbeat())
                    await heartbeat_job
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.warning("node_runtime_retry:" + type(error).__name__)
                await asyncio.sleep(1)
            finally:
                app.state.runtime_connected = False
                if heartbeat_job:
                    heartbeat_job.cancel()
                    await asyncio.gather(heartbeat_job, return_exceptions=True)
                if connection:
                    await connection.close()
    finally:
        pool.shutdown(wait=True)
