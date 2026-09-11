# NodoFlow — Prototipo
Sistema distribuido de procesamiento concurrente de tareas · UTO · Actividad 4.

## Estado real
Fase 6, Capa 2: camino feliz ejecutable. Ya admite tareas, conserva Task + Outbox atómicamente, asigna desde C-03 a un nodo disponible, ejecuta mediante RabbitMQ y un pool acotado, y guarda resultados consultables. La interfaz permite enviar un texto o crear tres ejemplos. La recuperación automática de intentos tras caída, retry funcional, drenaje y la evaluación experimental completa siguen pendientes; esta entrega no declara completada toda la Fase 6.

## Iniciar en Windows
Requiere Docker Desktop activo con contenedores Linux. Desde esta carpeta:

```powershell
./scripts/start.ps1 -Nodes 1
```

Para dos o tres nodos, usar `-Nodes 2` o `-Nodes 3`. El script detiene las réplicas sobrantes si se reduce la cantidad, conserva los volúmenes y espera las comprobaciones de salud. La primera ejecución descarga y construye las imágenes.

- Interfaz: http://localhost:14200
- API / documentación: http://localhost:18000/docs
- Readiness: http://localhost:18000/health/ready
- Prometheus: http://localhost:19090
- Grafana: http://localhost:13000 (usuario admin; contraseña local en .env).

`.env` se genera automáticamente con contraseñas aleatorias y está excluido del repositorio. Nunca subirlo. `.env.example` contiene los nombres y valores experimentales aprobados, sin secretos. Las contraseñas autogeneradas usan hexadecimal para ser seguras dentro de URLs; si se cambian manualmente, deben codificarse correctamente para su uso en URLs. Cambiar una contraseña no modifica automáticamente un volumen de base de datos ya inicializado.

## Detener conservando los datos
```powershell
docker compose --profile three stop
```

## Estructura y arquitectura
- `backend/nodoflow`: runtime Python/FastAPI; rol application (C-02/C-03) o node (C-05), Repository, API de tareas, dispatcher y consumidor de ejecución.
- `frontend`: Angular, servido por Nginx con proxy a la API.
- `compose.yaml`: PostgreSQL (C-06), RabbitMQ (C-04), aplicación, réplicas A/B/C y observabilidad (C-07).
- `observability`: Prometheus, integración RabbitMQ y fuente de datos Grafana.
- `scripts`: arranque reproducible.
- `backend/tests`: fallos de dependencias y frontera de acceso a datos.

Application es el único rol con credenciales de PostgreSQL. Los nodos dependen de RabbitMQ y del plano de control, sin enlaces entre nodos. La observabilidad no es dependencia de arranque de la aplicación. Todos los puertos publicados están limitados a localhost. Los nodos no publican puertos en el host.

`/health/live` verifica el proceso. `/health/ready` prueba conexiones reales con timeout y expone si el runtime funcional está conectado. Los nodos registran capacidad mediante heartbeat y ejecutan en un ThreadPoolExecutor reusable. C-03 selecciona un nodo vivo con capacidad libre; prioriza menor ocupación y desempata por identidad. Las asignaciones e intentos se crean transaccionalmente. La liveness deriva de la última señal y evita asignar a un nodo sin señal reciente; la recuperación de sus intentos interrumpidos aún está pendiente.

Baseline conservada: 4 workers/nodo, heartbeat 2 s, liveness 6 s, barrido previsto 1 s, timeout 2 s y máximo previsto de 3 intentos funcionales. El retry funcional y su barrido se implementarán en la capa de fallos. Actualmente failure_mode solo acepta none. El workload transforma un texto de hasta 500 caracteres a mayúsculas después de una espera controlada de 100–10000 ms; los ejemplos usan 4000 ms para hacer visible su ejecución. No se interpreta el texto como código.

## Verificación local de Python
```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
$env:PYTHONPATH = Join-Path $PWD 'backend'
./.venv/Scripts/python.exe -m pytest backend/tests -q
```

Las dependencias Python y Angular están fijadas en requirements.txt y package-lock.json. Las imágenes base usan etiquetas de versión explícitas. No son pins por digest; registrar los digests antes de las campañas experimentales. Los experimentos A–E todavía no se han ejecutado.

## Gobierno del proyecto
Plan Maestro y Log de Drive siguen siendo las referencias del proyecto. Los diagramas editables y sus imágenes están en docs/uml. Las copias locales del Plan y del Log se conservan fuera del repositorio; sus originales continúan en Drive. La sincronización con Drive de los artefactos previos está pendiente de aprobación; no se considera realizada.

## Documentación técnica consultada
- [Orden de arranque y health checks de Compose](https://docs.docker.com/compose/how-tos/startup-order/).
- [Lifespan de FastAPI](https://fastapi.tiangolo.com/advanced/events/).
- [Configuración de Pydantic](https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/).
