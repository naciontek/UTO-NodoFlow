# Verificación — Fase 6, Capa 2
Fecha: 2026-09-11.

## Resultado
Camino feliz ejecutable: formulario Angular → FastAPI → transacción Task + Outbox en PostgreSQL → dispatcher RabbitMQ → asignación por C-03 → cola del nodo A → ThreadPoolExecutor → reporte RabbitMQ → resultado autoritativo PostgreSQL → consulta automática en Angular.

La transformación concreta convierte el texto a mayúsculas y devuelve su longitud original. Es una implementación del workload determinista aprobado, no una nueva decisión arquitectónica.

## Verificación realizada
- Dos pruebas previas de salud/frontera de credenciales siguen aprobadas.
- Backend y frontend construidos en contenedores; los siete servicios de la configuración de un nodo están saludables.
- Migración Alembic 0001 creó nodes, tasks, attempts y outbox; claves únicas de idempotencia y de intento activo.
- scripts/verify_flow.py pasó contra servicios reales: entrada inválida 422, tipo no permitido 422, cuatro solicitudes equivalentes concurrentes producen una sola Task, reutilizar clave con otro payload responde 409, resultado correcto ejecutado por A, dos registros Outbox publicados, rechazo de resultado/started duplicado tras terminal y tarea inexistente 404.
- Tarea de integración: 986bce09-b3d8-42df-8069-76d35cce2ba6.
- Botón «Crear 3 ejemplos» probado desde el navegador. Las tres tareas pasaron a ejecución y luego a SUCCEEDED con resultados visibles:
  - 5aab48a0-1433-455a-809f-89e151d04fa0 → HOLA NODOFLOW, node-A_0.
  - 4a809377-f7ce-4b8b-9c56-e9b3b15aa6dd → PROCESAMIENTO DISTRIBUIDO, node-A_1.
  - f326d9fd-0049-437c-b8fe-a9f8242bbc3f → TRES TAREAS DE EJEMPLO, node-A_2.
- Botón «Ejecutar tarea» probado desde el formulario:
  - d1e19b18-7084-48bc-a050-3e459e4bc97b → HOLA NODOFLOW, node-A_0.
- Estado final observado: cinco tareas completadas, cero en proceso, nodo A disponible, 0/4 workers ocupados.
- Datos retenidos para consulta y trazabilidad, no resultados inventados.

## Avisos contentscript.js
Se localizaron los literales app-init-liveness, background-liveness y ObjectMultiplex - orphaned data en código de MetaMask instalada en Chrome (13.47.0); también hubo coincidencias en su instalación Edge. Es evidencia del origen probable en la extensión. No se modificó ni deshabilitó MetaMask y no se afirma haber reparado sus avisos. El flujo de NodoFlow fue comprobado en el navegador integrado.

## Límites
Esta es la Capa 2, no una auditoría completa de las capas 3–7 ni una campaña A–E. Se implementó el mínimo de pool, registro/heartbeat, scheduling, Outbox y transiciones requerido para el camino feliz sin contradecir la arquitectura.
- Los modos de fallo controlado distintos de none se rechazan por ahora.
- Recuperación automática de intentos interrumpidos, retry funcional finito y drenaje siguen pendientes.
- Una caída abrupta puede dejar un intento RUNNING; no usar todavía esta versión para afirmar recuperación.
- Falta instrumentación funcional completa y evaluación de escalamiento.
- Listado limitado a las últimas 100 tareas, con filtro de estado en la API.
- Readiness informa conectividad de infraestructura y un indicador de runtime; no es prueba de todos los invariantes.
