# Verificación — Fase 6, Capa 1
Fecha: 2026-09-11. Entorno: Windows, Docker Desktop con contenedores Linux.

- Repositorio local inicializado; sin remoto ni publicación.
- Docker Engine 29.6.1 y Compose 5.3.0 disponibles.
- Configuración Compose para tres nodos validada.
- Backend: 2 pruebas aprobadas. Una advertencia de deprecación de Starlette/AnyIO no impide ejecución.
- Frontend Angular compilado en contenedor. Versiones finales: framework/compiler-cli 20.3.31, build/CLI 20.3.37. npm reportó 0 vulnerabilidades al resolver el lockfile y al ejecutar npm ci.
- Arranque completo: nueve servicios saludables con A/B/C; ocho con A/B; siete con A.
- Identidades A, B y C verificadas en /health/ready de cada contenedor; cada nodo confirma RabbitMQ y application.
- API consultada a través del proxy de la interfaz: PostgreSQL=true, RabbitMQ=true, status=ready.
- Prometheus: application, node-a y rabbitmq en estado up. En esta capa su configuración de scrape cubre la topología de un nodo; ampliarla con B/C corresponde a la instrumentación posterior.
- Grafana responde a su endpoint de salud.
- Revisión visual en navegador: pantalla legible, mensaje de conexiones listas y botón funcional.
- Estado final: application, frontend, postgres, rabbitmq, node-a, prometheus y grafana encendidos; node-b y node-c detenidos.
- .env y .venv excluidos por .gitignore.

## Incidencias corregidas
1. Docker Desktop estaba apagado: se inició.
2. Resolución inicial de Angular seleccionaba un compilador incompatible: se fijaron versiones alineadas.
3. Dependencias Angular iniciales reportaban vulnerabilidades: se reemplazaron por parches de mantenimiento y se regeneró el lockfile.
4. Health check de Nginx con localhost fallaba por resolución local: se comprobó 127.0.0.1 y se corrigió la sonda.
5. Se fijó hostname de RabbitMQ para mantener estable la identidad sobre su volumen.

## Límites de esta evidencia
Son comprobaciones de infraestructura, no los experimentos A–E. No existen todavía tablas de dominio, admisión de tareas, scheduler, dispatcher funcional, workers activos, registro/heartbeat ni recuperación. La UI y /health/ready lo indican explícitamente. Los contenedores saludables no prueban procesamiento distribuido.
