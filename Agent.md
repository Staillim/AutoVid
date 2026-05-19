# Agent.md

## Proposito

Este archivo sirve como guia de continuidad para cualquier agente que tome el proyecto.

La idea no es solo "seguir programando", sino mantener el mismo ritmo de trabajo que ya venimos usando:

- revisar el estado real antes de tocar codigo
- avanzar por hitos pequenos pero cerrados
- verificar cada cambio con evidencia
- documentar todo paso a paso
- dejar siempre claro que se hizo, que falta y cual es el siguiente movimiento

## Forma en la que hemos venido trabajando

El proyecto se esta llevando como una construccion incremental con trazabilidad fuerte.

Patron actual de trabajo:

1. revisar el estado actual del repo y la documentacion existente
2. identificar el hito activo o el bloqueo real
3. hacer cambios concretos y acotados
4. verificar con tests, smoke tests o validaciones reales
5. registrar el resultado en documentacion de avance
6. cerrar dejando el siguiente paso recomendado

No estamos trabajando "por intuicion" ni acumulando cambios difusos. Cada avance debe quedar conectado con un entregable verificable.

## Documentos fuente que se deben revisar primero

Antes de continuar el trabajo, revisar siempre:

- `README.md`
- `docs/estado_actual_proyecto.md`
- `docs/progreso_desarrollo.md`
- `docs/smoke_test_render.md`
- `blueprint_motor_audiovisual.md`

Objetivo de cada uno:

- `README.md`: resumen del proyecto y prioridad de ingenieria
- `docs/estado_actual_proyecto.md`: fotografia honesta del estado actual
- `docs/progreso_desarrollo.md`: bitacora de hitos completados y verificaciones
- `docs/smoke_test_render.md`: procedimiento operativo para validaciones de render
- `blueprint_motor_audiovisual.md`: direccion arquitectonica grande del sistema

## Estado de trabajo que este agente debe asumir

El proyecto ya no esta en fase de idea. Tiene base tecnica real.

Situacion general asumida:

- backend base implementado
- contratos de dominio ya definidos
- pipeline de render inicial existente
- smoke test real ya contemplado como mecanismo de validacion
- documentacion de estado y progreso ya iniciada

La prioridad no es reescribir la arquitectura desde cero, sino continuar sobre la base existente con iteraciones bien cerradas.

## Ritmo esperado de ejecucion

Cada sesion debe intentar cerrar una unidad de trabajo completa.

Eso significa:

- no abrir frentes innecesarios en paralelo
- no dejar cambios grandes sin verificacion
- no marcar algo como terminado sin evidencia
- no pasar al siguiente hito sin registrar el resultado del anterior

Si una tarea es grande, dividirla en subhitos con entrega verificable.

## Regla de oro: documentar mientras se avanza

No dejar la documentacion para "despues".

Cuando se cierre un avance relevante, actualizar:

- `docs/progreso_desarrollo.md` para registrar el hito
- `docs/estado_actual_proyecto.md` si cambia la fotografia global del proyecto
- `README.md` si cambia el estado general o el siguiente objetivo inmediato

## Formato esperado para registrar avances

Cuando se complete un hito en `docs/progreso_desarrollo.md`, mantener esta estructura:

1. fecha
2. nombre del hito
3. que se entrego
4. como se verifico
5. bugs corregidos o decisiones tecnicas relevantes
6. lo siguiente

La verificacion debe ser concreta. Ejemplos validos:

- cantidad de tests pasando
- comando ejecutado
- artefactos generados
- endpoint verificado
- archivo exportado

Evitar frases vagas como:

- "parece funcionar"
- "quedo listo"
- "ya deberia estar bien"

## Como decidir el siguiente paso

El siguiente paso no se elige por comodidad, sino por impacto y continuidad.

Orden de preferencia:

1. desbloquear el pipeline principal del producto
2. cerrar huecos de persistencia o integracion real
3. fortalecer verificaciones
4. avanzar UI o capas secundarias cuando la base ya soporte ese paso

Si hay duda entre dos tareas, elegir la que:

- reduzca mas riesgo tecnico
- mejore mas la trazabilidad
- deje un resultado comprobable al final de la sesion

## Expectativas al tocar codigo

Antes de editar:

- entender el archivo y su rol en la arquitectura
- revisar si ya existe documentacion relacionada
- evitar duplicar logica o romper contratos ya definidos

Despues de editar:

- correr la verificacion mas cercana al cambio
- revisar si la documentacion quedo desactualizada
- dejar claro si el cambio cierra el hito o solo avanza una parte

## Expectativas de verificacion

Siempre que sea posible, validar con una de estas evidencias:

- tests unitarios
- smoke test
- verificacion de endpoints
- artefactos reales de salida
- chequeos de compatibilidad de paths o entorno

Si no se pudo verificar algo, debe quedar escrito de forma explicita junto con la razon.

## Lo que no se debe hacer

- avanzar varias capas del sistema sin cerrar ninguna
- asumir que algo funciona sin prueba
- cambiar contratos centrales sin reflejarlo en documentacion
- borrar contexto util de avances anteriores
- dejar un hito "casi terminado" sin explicar que falta

## Criterio de cierre de una sesion

Una sesion se considera bien cerrada cuando deja:

- codigo consistente
- evidencia de verificacion o una limitacion explicitada
- documentacion actualizada
- siguiente paso recomendado

## Instruccion final para cualquier agente que continue

Trabaja como si estuvieramos en una revision continua del avance.

Cada cambio debe responder estas preguntas:

1. que problema real resuelve
2. como se comprobo
3. donde quedo documentado
4. que habilita despues

Si al final de la sesion otra persona puede entrar al repo, leer la documentacion y entender exactamente en que estado quedamos, entonces el ritmo de trabajo se mantuvo bien.
