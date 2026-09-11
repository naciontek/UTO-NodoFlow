# NodoFlow — UML de la Actividad 4

Entrega del 11 de septiembre de 2026. Incluye los tres tipos UML obligatorios; el tipo secuencia se presenta en dos vistas ya previstas por el Log.

| Archivo | Contenido |
|---|---|
| 01-componentes | C-01..C-07, interfaces I-01..I-10, autoridades y canales |
| 02-secuencia-principal | Aceptación durable, Outbox, asignación, ejecución y consulta |
| 03-secuencia-recuperacion | Liveness, abandono, retry finito y rechazo de reporte obsoleto |
| 04-despliegue | Host académico, contenedores, protocolos y 1/2/3 nodos |

Cada vista incluye fuente editable `.puml`, imagen `.png` y vector `.svg`. Abra `index.html` para revisar las imágenes; abra el SVG individual para ampliar sin perder nitidez.

## Fuentes y precedencia

- [Plan Maestro original](https://drive.google.com/file/d/1_nX9ZcnIKOPl3JRNXzjtY93vkUkgzGHA/view).
- [Log original](https://drive.google.com/file/d/1S4G1l9lswU4hFGl-DrudJVUfBztpaH4s/view).
- La Fase 4 proporciona cuatro fuentes canónicas. Las precisiones de Fase 5.2 determinan la materialización vigente: C-03 selecciona nodo, RabbitMQ transporta mensajes y Prometheus usa pull/scrape. Los diagramas entregados aplican esas decisiones posteriores.
- Los originales recuperados se conservan en la carpeta local `contexto`. El Plan Maestro permanece sin modificar. Su sección histórica de estado no refleja los cierres posteriores; el avance más reciente consta en el Log.

## Alcance y trazabilidad

Los diagramas conservan C-03 como autoridad de decisión y C-06 como autoridad de estado; C-04 es reconciliable y C-07 no decide. Representan Producer–Consumer, Mediator, Observer, Retry, Repository y Transactional Outbox. No se agregan diagramas de clases, estados o casos de uso.

La secuencia de recuperación conserva task_id, crea un nuevo attempt_id y limita el retry funcional a tres intentos totales. La baseline usa cuatro workers por nodo y heartbeat cada dos segundos, con seis segundos sin señal válida y barrido cada segundo. La selección de nodo depende de elegibilidad/capacidad; no se fija un nuevo algoritmo de scheduling.

Las secuencias representan el caso válido y la recuperación principal, no un catálogo de todos los errores. El orden dibujado es un recorrido posible: no se presupone orden global ni entrega exactly-once. Las publicaciones críticas se muestran después de persistir estado/Outbox, conforme a la regla de publicación durable. Los nombres de operaciones son ilustrativos, no contratos de API nuevos.

Verificación: compilación local con PlantUML 1.2025.10, generación de cuatro SVG y cuatro PNG y revisión visual. Esto verifica los artefactos UML; no constituye una prueba del prototipo ni evidencia experimental. La implementación de Fase 6 no se inició.
