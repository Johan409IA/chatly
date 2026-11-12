# Chatly — Roadmap de desarrollo actualizado

> **Nombre vigente:** Chatly  
> **Plataforma:** aplicación web responsive e instalable como PWA.  
> **Idioma de la V1:** español.  
> **Base funcional:** 179 decisiones aprobadas mediante Grill Me.  
> **Fecha objetivo de entrega:** 30 de abril de 2027.  
> **Estado:** alineado con el diseño social cerrado; implementación pendiente de las migraciones `0013_descubrimiento_social` y `0014_social_cron`.

---

## 1. Visión y objetivo de entrega

**Chatly** será una aplicación de mensajería colaborativa inspirada en WhatsApp, con conversaciones privadas y grupales, encuestas/votaciones integradas y una funcionalidad social para descubrir personas y grupos mediante intereses compartidos.

La V1 debe demostrar que el equipo puede implementar lógica de negocio, autenticación, autorización, persistencia, comunicación en tiempo real, trazabilidad y sincronización offline básica, además de recomendaciones sociales sencillas sin inteligencia artificial.

La entrega se considerará lista cuando exista una URL pública gratuita con:

- Cinco cuentas de demostración preparadas y datos iniciales para que la aplicación no esté vacía.
- Registro de nuevos usuarios con correo real y confirmación obligatoria.
- Perfiles editables y búsqueda directa de usuarios.
- Selección opcional de intereses desde un catálogo organizado por categorías.
- Descubrimiento de personas por intereses compartidos, con controles de visibilidad.
- Conversaciones privadas y grupales funcionales.
- Grupos privados por defecto que pueden hacerse descubribles por su administrador.
- Búsqueda y recomendaciones de grupos, con solicitudes de incorporación.
- Mensajería, reacciones, respuestas, edición, eliminación lógica y confirmaciones de lectura.
- Encuestas con votación, resultados en tiempo real y cierre.
- Presencia y estado de escritura.
- Notificaciones visuales internas para mensajes y solicitudes de unión.
- Historial y permisos coherentes con los periodos de membresía.
- Auditoría de operaciones importantes.
- PWA instalable y modo offline limitado a la experiencia acordada.
- Pruebas de aceptación superadas y documentación de entrega.

No se exige soportar miles de usuarios, ofrecer SLA ni operar como servicio comercial.

### Alcance social que debe respetarse

- No se implementarán amistades, seguidores, solicitudes de contacto ni solicitudes para iniciar conversaciones.
- No se implementarán bloqueo, reportes ni moderación avanzada en V1.
- Las recomendaciones se basarán exclusivamente en intereses coincidentes; no se usará IA ni un algoritmo complejo.
- La sección social reutilizará perfiles, conversaciones y grupos existentes. No se creará una entidad independiente de «Comunidad» ni un sistema social paralelo.

## 2. Supuestos de planificación

- **Ramas:** `main` para versiones estables, `develop` para integración y ramas `feature/*` para trabajo funcional.
- **Base de datos:** Supabase PostgreSQL en la nube. Alembic administra el esquema propio de Chatly; no se duplicarán las migraciones de esas tablas mediante Supabase CLI.
- **Conexión PostgreSQL:** Session Pooler de Supabase para desarrollo y Render, sujeto a validar la configuración del proyecto. `DATABASE_URL` se reserva para DDL/migraciones; `APP_DATABASE_URL` es el runtime y `TEST_DATABASE_URL` las pruebas, ambos con `chatly_app` sin `BYPASSRLS`.
- **Backend:** Reflex como framework full-stack, con endpoints FastAPI integrados. No se desplegará un segundo servidor FastAPI.
- **Realtime:** Postgres Changes para cambios persistidos, Presence para online/offline y Broadcast para `escribiendo…`. Una pequeña integración JavaScript del frontend administrará las suscripciones; las reglas de negocio y la autorización final permanecerán en Python/backend y RLS.
- **Notificaciones sociales:** los eventos de solicitudes se entregarán mediante los canales/eventos privados definidos en `realtime-events.md`; no se expondrán solicitudes a usuarios ajenos.
- **Sin Redis:** una sola instancia del backend para la demostración.
- **Offline:** últimos 50 mensajes por conversación en IndexedDB; al abrir hacia atrás se consultarán 30 mensajes adicionales por página mientras haya conexión. La cola offline se limita a mensajes de texto. No se amplía el alcance offline a recomendaciones ni a solicitudes de unión.
- **Descubrimiento:** las recomendaciones se recalculan al abrir o actualizar Descubrir. No se recalculan en vivo mientras el usuario edita sus intereses.
- **Privacidad:** los perfiles y los grupos tienen controles de visibilidad independientes. Un perfil público no convierte en públicos los grupos que administra, ni viceversa.

### Decisiones técnicas cerradas que condicionan el roadmap

| Tema | Decisión |
|---|---|
| Catálogo de intereses | `GET /api/interests` público (sin sesión) para el registro; el resto de endpoints sociales exige usuario verificado. |
| Orden de Descubrir | Coincidencias descendentes y desempate `md5(seed || ':' || id)`; cursor firmado con `seed`, `after_count`, `after_hash`, `after_id`. |
| Caducidad | Job de `pg_cron` cada 15 min como `chatly_app`; `app.expire_pending_join_requests()` expira y publica `join_request.resolved`. |
| Broadcast social | `app.publish_social_event(event, target_user_id, payload)` `SECURITY DEFINER`, propiedad del rol de migraciones, `EXECUTE` solo a `chatly_app`. |
| Límites | Descubrir 30/min, crear solicitud 10/min, consultar la propia 60/min. |
| Personas | `PersonRecommendation` no incluye `online`; el cliente lo obtiene por Presence. |
| Solicitudes | `solicitudes_union` solo grupos mediante `tipo='group'` + FK compuesta `(conversacion_id, tipo)` con `uq_conversaciones_id_tipo`. |
| Identidad y rol | `app.current_actor_id()` `SECURITY DEFINER`; `chatly_app` no hereda `authenticated` (`revoke authenticated from chatly_app`). |
| Migraciones | `0005_identidad_rol`, luego `0005b_intereses` (catálogo y selección en el registro) y `0006`–`0012` base y `0013`/`0014` social. |

## 3. Stack acordado


| Área                   | Tecnología                                | Responsabilidad                                                                     |
| ---------------------- | ----------------------------------------- | ----------------------------------------------------------------------------------- |
| Lenguaje               | Python 3.13.7                             | Backend y lógica de negocio                                                         |
| Entorno y dependencias | uv                                        | Entorno virtual, dependencias y lockfile                                            |
| Framework web          | Reflex                                    | Interfaz, páginas, componentes, estado y servidor de la aplicación                  |
| API REST               | FastAPI integrado en Reflex               | Endpoints HTTP propios                                                              |
| Validación             | Pydantic                                  | Validación de entrada y salida                                                      |
| ORM                    | SQLAlchemy 2 (async)                      | Acceso a PostgreSQL                                                                 |
| Driver PostgreSQL      | Psycopg 3                                 | Conexión a Supabase PostgreSQL                                                      |
| Migraciones            | Alembic                                   | Esquema, restricciones, índices y SQL de políticas                                  |
| Base de datos          | Supabase PostgreSQL                       | Persistencia de Chatly                                                              |
| Autenticación          | Supabase Auth                             | Registro, login, confirmación, refresh y recuperación                               |
| Tiempo real            | Supabase Realtime                         | Postgres Changes, Presence y Broadcast                                              |
| Archivos               | Supabase Storage                          | Fotografías en bucket privado                                                       |
| Correo                 | Brevo SMTP Free                           | Confirmación y recuperación de cuentas; verificar límites vigentes antes de la demo |
| Pruebas                | pytest, pytest-asyncio, pytest-cov, httpx | Pruebas unitarias e integración                                                     |
| Calidad                | Ruff                                      | Lint y formato                                                                      |
| Offline/PWA            | Service Worker e IndexedDB                | Caché y cola local de mensajes                                                      |
| Despliegue             | Render Free                               | Aplicación web y backend                                                            |


**Nota de seguridad para RLS con conexión PostgreSQL directa:** el backend debe verificar el JWT de Supabase y establecer el contexto del usuario dentro de cada transacción (por ejemplo, mediante una variable local de transacción). El rol de conexión no debe tener `BYPASSRLS`. El equipo debe probar que el contexto no se filtra entre peticiones al reutilizar conexiones del pool. No debe asumirse que `auth.uid()` recibe automáticamente el JWT cuando se utiliza una conexión PostgreSQL directa.

## 4. Calendario general y principales hitos

Se conserva el calendario base y la fecha de entrega. La funcionalidad social se distribuye en las iteraciones pendientes: sus datos se preparan junto a perfiles y grupos; las notificaciones se incorporan a Realtime; la experiencia de Descubrir se implementa en la iteración de seguridad/integración social; y sus escenarios se incluyen en los datos demo y pruebas E2E.


| Hito                                              | Fechas                  | Resultado esperado                                                                                    |
| ------------------------------------------------- | ----------------------- | ----------------------------------------------------------------------------------------------------- |
| M0 — Repositorio preparado                        | 2–8 nov 2026            | Proyecto reproducible, Reflex arranca, dependencias, Git y estructura básica                          |
| M1 — Fundamentos técnicos                         | 9–22 nov 2026           | Arquitectura, configuración, conexión DB, Alembic y prueba de contexto RLS                            |
| M2 — Identidad, perfiles e intereses              | 23 nov–6 dic 2026       | Auth, confirmación de correo, perfil, alias, búsqueda, catálogo e intereses personales                |
| M3 — Conversaciones, grupos y datos sociales      | 7–20 dic 2026           | Chats privados, grupos, membresías históricas, visibilidad de grupos e infraestructura de solicitudes |
| M4 — Mensajería funcional                         | 21 dic 2026–17 ene 2027 | Mensajes, edición, eliminación, respuestas, reacciones y lecturas                                     |
| M5 — Tiempo real y notificaciones                 | 18–31 ene 2027          | Postgres Changes, Presence, Broadcast, reconexión y notificaciones sociales                           |
| M6 — Encuestas                                    | 1–14 feb 2027           | Encuestas, votos, cambios de voto y resultados en vivo                                                |
| M7 — Descubrimiento social, auditoría y seguridad | 15–28 feb 2027          | Personas, grupos descubribles, solicitudes de unión, RLS y casos sociales probados                    |
| M8 — Storage y datos demo                         | 1–14 mar 2027           | Fotografías privadas, SMTP operativo y cinco cuentas/datos de prueba, incluidos escenarios sociales   |
| M9 — PWA y offline                                | 15–28 mar 2027          | Instalación PWA, caché de 50 mensajes y cola offline idempotente                                      |
| M10 — Integración y congelación funcional         | 29 mar–11 abr 2027      | Flujos completos, pruebas end-to-end y congelación de funcionalidades                                 |
| M11 — Despliegue y aceptación                     | 12–25 abr 2027          | Render, configuración de demo, documentación y ensayo                                                 |
| M12 — Entrega                                     | 26–30 abr 2027          | Código congelado, versión etiquetada y demostración final                                             |


---

# 5. Roadmap detallado por iteraciones

## Fase 0 — Preparación del proyecto

**Fechas:** 2–8 de noviembre de 2026  
**Objetivo:** que los cuatro integrantes puedan clonar el repositorio, instalar el entorno y ejecutar Chatly con los mismos comandos.

### Tareas

- [x] Crear el repositorio GitHub `Chatly`.
- [x] Definir `main` y `develop`. <!-- develop creado desde main; protección de main descartada por decisión del equipo -->
- [x] Inicializar el proyecto con Python 3.13.7 y uv.
- [x] Inicializar Reflex con una plantilla vacía.
- [x] Instalar dependencias: Reflex, FastAPI (importación directa para endpoints), Pydantic, SQLAlchemy 2, Psycopg 3, Alembic, Pydantic Settings, PyJWT y herramientas de pruebas/calidad.
- [x] Declarar `@supabase/supabase-js` mediante la configuración de paquetes frontend de Reflex (`frontend_packages`); no se creó un proyecto Node independiente.
- [x] Crear estructura inicial de `pages`, `components`, `state`, `backend`, `tests`, `docs` y `assets`.
- [x] Crear `.env.example` y excluir `.env` del control de versiones.
- [x] Inicializar Alembic con plantilla asíncrona.
- [x] Configurar Ruff y pytest.
- [x] Crear una ruta de salud `/api/health`.
- [x] Crear un README con instalación, ejecución local y convenciones de colaboración.
- [x] Crear proyecto Supabase Cloud y registrar de forma segura URL, publishable key y datos de conexión.

> **Nota:** CI/CD en GitHub y la protección automática de `main` fueron descartadas por decisión del equipo. El resto de los criterios de salida se verificaron localmente.

### Entregables

- [x] Repositorio compartido.
- [x] Proyecto Reflex mínimo ejecutable.
- [x] `pyproject.toml`, `uv.lock`, `.python-version`, `rxconfig.py` y `alembic.ini`.
- [x] `.env.example` y README.
- [x] Estructura de carpetas acordada.

### Criterios de salida

- [x] Se puede ejecutar `uv sync` y `uv run reflex run`.
- [x] La aplicación abre localmente.
- [x] `uv run pytest` y `uv run ruff check .` finalizan correctamente.
- [x] No hay secretos en Git.
- [x] El repositorio tiene protección básica de `main` y los PR se integran a `develop`. (protección activada: PRs obligatorios, sin push directo; admins pueden saltarla)

## Iteración 1 — Arquitectura y cimientos de backend

**Fechas:** 9–22 de noviembre de 2026  
**Objetivo:** construir la base técnica antes de implementar funcionalidades visibles.

### Tareas

- [x] Definir arquitectura por capas: páginas/componentes, estados Reflex, API, servicios, repositorios, modelos e integraciones.
- [x] Crear configuración central con Pydantic Settings.
- [x] Implementar engine SQLAlchemy asíncrono, pool, sesiones y manejo de transacciones.
- [x] Configurar Psycopg 3 y conexión Supabase Session Pooler.
- [x] Configurar `target_metadata` de Alembic y convenciones de nombres para constraints e índices.
- [x] Crear modelos base y convenciones comunes: UUID, timestamps, estado lógico y campos de auditoría técnica.
- [x] Diseñar y probar el mecanismo de identidad RLS para conexiones PostgreSQL directas.
- [x] Verificar el aislamiento de identidad entre transacciones con pool de conexiones.
- [x] Crear manejo centralizado de errores de API y respuestas consistentes.
- [x] Añadir logs de aplicación sin exponer tokens, contraseñas ni datos privados.
- [x] Crear pruebas de conexión, transacción, rollback y contexto RLS.
- [x] Elaborar primer diagrama de arquitectura y flujo de una petición.

### Entregables

- Arquitectura técnica inicial.
- Conexión SQLAlchemy operativa.
- Alembic configurado y primera migración de infraestructura (si aplica).
- Mecanismo RLS probado en un caso mínimo.
- Pruebas base y diagrama de arquitectura.

### Criterios de salida

- Una petición autenticada simulada solo puede consultar filas permitidas en el test RLS.
- Dos peticiones consecutivas con usuarios distintos no comparten contexto.
- Las transacciones liberan correctamente conexiones del pool.
- El backend puede ejecutar consultas contra Supabase sin usar credenciales privilegiadas en el navegador.

## Iteración 2 — Autenticación, perfiles e intereses personales

**Fechas:** 23 de noviembre–6 de diciembre de 2026  
**Objetivo:** permitir que los usuarios creen cuentas verificadas, administren su perfil y configuren los intereses que se utilizarán en el descubrimiento social.

### Tareas existentes

- [x] Configurar Supabase Auth: correo/contraseña, confirmación obligatoria y recuperación.
- [x] Configurar URLs de redirección de desarrollo (`localhost`) y futura demo.
- [ ] Configurar SMTP externo en Supabase Auth y probar confirmación/recuperación con direcciones reales. <!-- SMTP Brevo configurado; falta probar con direcciones reales -->
- [x] Revisar límites de Auth y del proveedor de correo; registrar el procedimiento de reenvío de confirmación. <!-- architecture.md §5.5 -->
- [x] Implementar verificación de JWT en backend mediante claves públicas/JWKS y validaciones de issuer, audience/claims, firma y expiración según configuración.
- [x] Implementar guardas de rutas y estado de sesión en Reflex. <!-- require_verified pendiente de la tabla profiles -->

### Tareas pendientes de identidad y perfiles

- [x] Crear `perfiles` y `contactos_usuario` (migración `0002_perfiles` aplicada).
- [ ] Implementar creación/sincronización de perfil al registrar usuario.
- [ ] Implementar normalización del correo y búsqueda exacta sin exponerlo en resultados.
- [ ] Implementar alias único, formato 3–20 caracteres y normalización case-insensitive.
- [ ] Implementar cambio de alias con periodo de espera de 30 días y auditoría.
- [ ] Crear pantallas en español: registro, login, confirmación pendiente, reenvío, recuperación y perfil.
- [ ] Crear pruebas de confirmación bloqueante, expiración de sesión, alias duplicado y privacidad del correo.

### Nuevas tareas de intereses y visibilidad personal

- [x] Incorporar al modelo de datos el catálogo de categorías e intereses y la relación entre usuarios e intereses. <!-- migración 0005b_intereses -->
- [x] Preparar el catálogo inicial de intereses desde los datos de la aplicación; los usuarios no podrán crear intereses personalizados. <!-- semilla en 0005b_intereses -->
- [x] Establecer un máximo de 10 intereses por usuario. <!-- validación 422 interest_limit_exceeded -->
- [x] Añadir la configuración `visibilidad_publica` al perfil, activada por defecto e independiente de la visibilidad de los grupos. <!-- columna en 0005b_intereses; la UI llega con 0013 -->
- [x] Permitir seleccionar intereses durante el registro, sin obligar al usuario a elegir ninguno. <!-- bloque opcional en /register -->
- [x] Presentar las categorías de forma expandible y los intereses concretos como etiquetas seleccionables. <!-- accordion por categoría con contador N/10 -->
- [ ] Permitir modificar los intereses desde el perfil y mostrar el límite de selección (por ejemplo, `3/10`). <!-- requiere PUT /api/me/interests -->
- [ ] Permitir desactivar/activar la visibilidad pública desde los ajustes.
- [ ] Definir las respuestas del perfil público: mostrar todos los intereses únicamente cuando la visibilidad pública esté activada; ocultarlos cuando esté desactivada.
- [ ] Mantener la búsqueda directa por alias/correo aunque la visibilidad pública esté desactivada; nunca devolver el correo en los resultados.
- [ ] Asegurar que no se recomiende a usuarios sin intereses configurados.
- [ ] Añadir pruebas para selección opcional, máximo de diez, edición de intereses y visibilidad independiente. <!-- la parte de registro está cubierta; falta la de edición -->

### Entregables

- Flujos de registro/login/confirmación/recuperación.
- Perfiles y búsqueda.
- Catálogo de intereses y selección opcional en registro/perfil.
- Preferencia de visibilidad pública de perfil.
- Migraciones y políticas iniciales.
- Pruebas de autenticación, perfiles, intereses y privacidad.

### Criterios de salida

- Un usuario no verificado no puede acceder a funcionalidades de chat ni a Descubrir.
- El JWT se verifica en backend y el actor se deriva del token, no de un `user_id` enviado por el cliente.
- La búsqueda por correo exige coincidencia exacta y no revela el correo.
- No pueden existir alias duplicados ignorando mayúsculas/minúsculas.
- El usuario puede omitir los intereses durante el registro y configurarlos después.
- Un usuario no puede seleccionar más de diez intereses.
- La visibilidad del perfil está activada por defecto y puede desactivarse sin ocultar los grupos que administra.

## Iteración 3 — Conversaciones, grupos y membresías

**Fechas:** 7–20 de diciembre de 2026  
**Objetivo:** construir el núcleo de conversaciones, aplicar las reglas históricas de pertenencia y dejar preparada la estructura de los grupos descubribles y las solicitudes de unión.

### Tareas existentes

- [ ] Crear `conversaciones` con tipos `direct` y `group`.
- [ ] Crear `miembros_conversacion` con periodos de entrada/salida, rol, actor que añadió/expulsó y estado.
- [ ] Crear `preferencias_conversacion` para ocultar chats de forma individual.
- [ ] Implementar restricción de una conversación privada por pareja de usuarios.
- [ ] Implementar creación de grupos con mínimo 3 y máximo 10 integrantes.
- [ ] Implementar administrador único y restricciones de operación.
- [ ] Implementar incorporación directa y prevención de duplicados activos.
- [ ] Implementar expulsión, salida y opción «Salir y eliminar».
- [ ] Implementar sucesión automática del administrador al integrante activo con mayor antigüedad.
- [ ] Implementar conservación de periodos históricos y reincorporación.
- [ ] Implementar archivo definitivo cuando el último integrante sale.
- [ ] Implementar modificación de nombre por el administrador y avatar generado.
- [ ] Generar mensajes de sistema para creación, incorporaciones, expulsiones, salidas, cambio de admin y cambio de nombre.
- [ ] Implementar visibilidad por periodo: antiguos integrantes solo consultan mensajes de sus periodos.
- [ ] Crear pruebas para grupos con 3, 2 y 1 integrante, expulsión, salida, reincorporación, sucesión y ocultación.

### Nuevas tareas de datos para grupos descubribles y solicitudes

- [ ] Ampliar el modelo de `conversaciones` con `descripcion` y `es_descubrible` (nombres definidos en `database-schema.md`).
- [ ] Establecer que los grupos se crean privados por defecto; solo el administrador actual puede cambiar su visibilidad.
- [ ] Crear la relación entre grupos e intereses; cada grupo descubrible deberá tener entre 1 y 5 intereses.
- [ ] Establecer que para activar la visibilidad descubrible el grupo debe tener descripción de 10–300 caracteres e intereses asociados.
- [ ] Permitir al administrador modificar la descripción y los intereses del grupo mientras mantenga las validaciones acordadas.
- [ ] Incorporar la entidad de solicitudes de unión con estados `pendiente`, `aceptada`, `rechazada` y `expirada`, fechas y referencias a solicitante/grupo/administrador que resolvió.
- [ ] Definir y probar la regla de una sola solicitud pendiente global por usuario; impedir duplicados pendientes para el mismo usuario y grupo.
- [ ] Implementar la caducidad automática después de 14 días sin respuesta.
- [ ] Preparar las restricciones transaccionales para impedir superar diez integrantes cuando coincidan solicitudes aceptadas e incorporaciones directas.
- [ ] Conservar las solicitudes históricas para trazabilidad; no crear una pantalla «Mis solicitudes».
- [ ] Incorporar estas entidades y campos al diagrama ER y a las migraciones Alembic.
- [ ] Reforzar en la base que `solicitudes_union` solo apunte a grupos: columna `tipo='group'` y FK compuesta `(conversacion_id, tipo)` con `uq_conversaciones_id_tipo`.
- [ ] Aplicar `0013_descubrimiento_social` al cerrar la iteración, con RLS, grants y pruebas negativas.

### Entregables

- Conversaciones privadas y grupales.
- Gestión completa de membresías.
- Preferencias individuales de visibilidad.
- Mensajes de sistema.
- Estructura de datos para perfiles/intereses, grupos descubribles e incorporaciones solicitadas.
- Pruebas de reglas de grupos y restricciones de integridad.

### Criterios de salida

- No se crean chats privados duplicados.
- Un grupo no supera diez integrantes activos ni se crea con menos de tres.
- Solo existe un administrador activo.
- Un antiguo integrante no accede a mensajes de periodos en los que no perteneció al grupo.
- «Salir y eliminar» no afecta la conversación de los demás.
- Un grupo es privado por defecto y solo su administrador puede publicarlo.
- Un grupo no puede publicarse sin descripción válida e intereses asociados.
- La base impide solicitudes pendientes duplicadas y más de una solicitud pendiente global por usuario.

## Iteración 4 — Mensajería esencial

**Fechas:** 21 de diciembre de 2026–3 de enero de 2027  
**Objetivo:** enviar, guardar, consultar y paginar mensajes de texto.

### Tareas

- [ ] Crear `mensajes` con tipos `text`, `system` y `poll` (el tipo `poll` se completará en la iteración de encuestas).
- [ ] Definir autoría, conversación, timestamps, estado lógico y referencia de respuesta.
- [ ] Implementar `MessageRepository` y `MessageService`.
- [ ] Implementar endpoint/acción para enviar mensajes con máximo 4.000 caracteres.
- [ ] Implementar consulta cronológica con cursor: 50 últimos mensajes al abrir y 30 adicionales al cargar hacia arriba.
- [ ] Implementar orden estable para mensajes con timestamps iguales.
- [ ] Implementar respuesta a mensaje y visualización de referencia.
- [ ] Crear interfaz de conversación, burbujas, compositor y lista de mensajes.
- [ ] Implementar estado de envío: pendiente de respuesta del servidor y confirmado con ✓.
- [ ] Añadir controles de autorización para leer/escribir según membresía y periodo.
- [ ] Crear pruebas de longitud, orden, paginación, autoría y permisos.

### Entregables

- Chat privado y grupal capaz de enviar y consultar mensajes persistidos.
- Interfaz de conversación inicial.
- Paginación por cursor.
- Pruebas de mensajes y permisos.

### Criterios de salida

- Dos usuarios autorizados pueden intercambiar mensajes guardados en PostgreSQL.
- Los mensajes se ordenan de forma estable.
- La respuesta a un mensaje conserva su referencia.
- Los usuarios fuera del periodo de membresía no pueden consultar ni enviar mensajes en ese grupo.

**Nota de calendario:** esta iteración coincide con fiestas de fin de año. Si la disponibilidad baja, priorizar persistencia y envío/lectura; dejar el refinamiento visual para la siguiente iteración.

## Iteración 5 — Edición, eliminación, reacciones y lectura

**Fechas:** 4–17 de enero de 2027  
**Objetivo:** completar las interacciones principales de mensajería.

### Tareas

- [ ] Crear `versiones_mensaje` y almacenar la versión anterior antes de cada edición.
- [ ] Implementar edición de mensajes propios sin límite de tiempo mientras el usuario sea miembro activo.
- [ ] Mostrar etiqueta «editado» y conservar solo la versión vigente en la vista del chat.
- [ ] Implementar eliminación lógica para todos, mostrando «Se eliminó un mensaje».
- [ ] Asegurar que la consulta normal no exponga el contenido eliminado.
- [ ] Mantener respuestas existentes cuando se elimina el mensaje original; mostrar marcador en la referencia.
- [ ] Crear `reacciones_mensaje` con los siete emojis acordados.
- [ ] Implementar una reacción activa por usuario/mensaje; cambiar actualiza y eliminar marca borrado lógico.
- [ ] Definir `last_read_message_id` por participante y periodo de membresía.
- [ ] Implementar contador de no leídos y confirmación ✓✓ según los integrantes elegibles al momento del envío.
- [ ] Marcar leído cuando la conversación esté abierta y la pestaña visible.
- [ ] Incluir mensajes de sistema en historial, no leídos y confirmaciones.
- [ ] Ordenar la lista de conversaciones por actividad más reciente.
- [ ] Implementar notificaciones visuales internas para mensajes nuevos, sin push ni sonido.
- [ ] Crear pruebas de edición, eliminación, versiones, reacciones, lectura y usuarios que salen/entran.

### Entregables

- Mensajería completa según reglas de V1.
- Confirmaciones y contadores de lectura.
- Historial de versiones.
- Pruebas de los casos límite.

### Criterios de salida

- Editar conserva versión anterior y muestra «editado».
- Eliminar no borra físicamente ni revela el contenido en consultas normales.
- Solo puede existir una reacción vigente por usuario y mensaje.
- Las confirmaciones de lectura respetan las membresías al momento del envío.

## Iteración 6 — Supabase Realtime, presencia y notificaciones sociales

**Fechas:** 18–31 de enero de 2027  
**Objetivo:** actualizar las interfaces sin polling y distribuir los eventos sociales privados necesarios.

### Tareas

- [ ] Configurar `@supabase/supabase-js` dentro del frontend administrado por Reflex.
- [ ] Implementar módulo JS de inicialización, ciclo de vida y limpieza de canales.
- [ ] Configurar Postgres Changes para mensajes, cambios de mensajes, reacciones, votos y eventos persistidos necesarios.
- [ ] Habilitar únicamente las tablas necesarias en la publicación `supabase_realtime`.
- [ ] Configurar políticas de autorización de Realtime basadas en membresías y periodos.
- [ ] Implementar Presence para online/offline, soportando varias pestañas/sesiones.
- [ ] Implementar Broadcast para `escribiendo…` con expiración de cinco segundos.
- [ ] Suscribir/desuscribir al cambiar de conversación o cerrar sesión.
- [ ] Gestionar reconexión, re-suscripción, eventos duplicados y eventos fuera de orden.
- [ ] Implementar actualización de JWT y expiración aproximada de diez minutos según configuración acordada.
- [ ] Al expulsar a un usuario, retirar la suscripción en cliente y hacer que el backend/DB impida nuevas lecturas y eventos; probar la ventana de autorización de conexiones ya establecidas.
- [ ] Crear pruebas con 3–5 sesiones/navegadores simultáneos.

### Nuevas tareas de eventos sociales

- [ ] Incorporar eventos/notificaciones privados para solicitud de unión recibida por el administrador.
- [ ] Notificar al solicitante cuando su solicitud sea aceptada, rechazada o expire.
- [ ] Propagar el cambio de administrador para que el nuevo administrador pueda gestionar las solicitudes pendientes.
- [ ] Propagar la revocación de visibilidad de un grupo para retirar su presencia de resultados externos sin afectar a sus integrantes.
- [ ] Reflejar cambios de visibilidad pública del perfil en los resultados de descubrimiento; el backend seguirá siendo la fuente de verdad.
- [ ] Utilizar Presence para mostrar el estado online en las tarjetas de personas cuando esté disponible.
- [ ] No emitir un evento por cada cambio de interés: las recomendaciones se recalculan al abrir Descubrir o actualizar resultados.
- [ ] Añadir los nuevos eventos y sus permisos a `realtime-events.md` y `authorization-matrix.md`.

### Entregables

- Mensajes y cambios persistidos visibles en tiempo real.
- Presencia y escritura.
- Notificaciones internas de solicitudes de unión.
- Suscripciones autorizadas y pruebas multiusuario/reconexión.

### Criterios de salida

- Un mensaje guardado por un usuario aparece en los otros clientes autorizados sin recargar.
- Usuarios externos o expulsados no reciben nuevos eventos autorizados.
- La presencia refleja varias sesiones de un mismo usuario.
- El indicador de escritura desaparece al dejar de recibir eventos durante cinco segundos.
- Las notificaciones sociales solo llegan a los usuarios autorizados.

## Iteración 7 — Encuestas y votaciones

**Fechas:** 1–14 de febrero de 2027  
**Objetivo:** completar la función diferenciadora de Chatly.

### Tareas

- [ ] Crear `encuestas`, `opciones_encuesta` y `votos_encuesta`.
- [ ] Relacionar cada encuesta con un mensaje de tipo `poll` en la conversación.
- [ ] Validar pregunta de 5–200 caracteres y opciones de 1–80 caracteres.
- [ ] Restringir encuestas a 2–5 opciones distintas (normalizadas sin distinguir mayúsculas/minúsculas).
- [ ] Permitir crear encuesta a cualquier miembro activo.
- [ ] Permitir editarla únicamente a su creador antes del primer voto.
- [ ] Bloquear opciones y pregunta después del primer voto.
- [ ] Implementar un voto vigente por usuario/encuesta mediante restricción única.
- [ ] Permitir cambiar el voto mientras la encuesta esté abierta y conservar el cambio en auditoría.
- [ ] Mostrar conteo, barras y quién votó cada opción.
- [ ] Implementar actualización de resultados en tiempo real.
- [ ] Permitir cerrar al creador; si el creador ya no pertenece al grupo, permitir cerrar al administrador actual.
- [ ] Cerrar encuestas automáticamente cuando se archive el grupo.
- [ ] Conservar votos aunque el participante abandone el grupo.
- [ ] Implementar eliminación lógica de encuesta solo antes del primer voto.
- [ ] Crear pruebas de duplicados, cambios de voto, cierre, salida de creador y archivo de grupo.

### Entregables

- Encuestas como mensajes del chat.
- Votación y resultados en vivo.
- Reglas de edición/cierre.
- Pruebas de integridad de votos.

### Criterios de salida

- No existe más de un voto vigente por usuario y encuesta.
- Los resultados se actualizan en todos los participantes autorizados.
- Las encuestas cerradas no aceptan nuevos votos ni cambios.
- Los votos históricos siguen contando después de una salida.

## Iteración 8 — Descubrimiento social, auditoría e integridad

**Fechas:** 15–28 de febrero de 2027  
**Objetivo:** implementar la experiencia de Descubrir y completar la revisión de seguridad, RLS e integridad de los nuevos recursos sociales y los módulos existentes.

### A. Descubrimiento de personas

- [ ] Crear la sección `Descubrir` con apartados `Personas` y `Grupos`, sin añadir una sección independiente de amistades o contactos.
- [ ] Implementar recomendaciones de personas usando coincidencia directa de intereses, sin IA.
- [ ] Recomendar solo perfiles con visibilidad pública activa, al menos un interés seleccionado y al menos una coincidencia con el usuario actual.
- [ ] Excluir personas con quienes ya exista una conversación privada; permitir que aparezcan personas que comparten uno de los grupos del usuario si aún no hay chat privado.
- [ ] Ordenar por número de intereses coincidentes; los empates se ordenan con `md5(seed || ':' || id)` y el cursor firmado conserva la semilla mientras se navega por la misma lista.
- [ ] Recalcular recomendaciones al abrir Descubrir o actualizar resultados, no mientras el usuario modifica sus intereses.
- [ ] Mostrar 20 resultados inicialmente y permitir cargar otros 20 con `Ver más`.
- [ ] Mostrar en cada tarjeta fotografía, nombre visible, intereses compartidos y estado online cuando esté disponible (el `online` se obtiene por Presence; el DTO REST no lo incluye). No mostrar alias ni un contador/texto adicional de coincidencias en la tarjeta.
- [ ] Al seleccionar una tarjeta, abrir el chat privado; reutilizar la conversación existente si la hay y crearla en la base de datos solo al enviar el primer mensaje.
- [ ] Permitir consultar el perfil completo desde la fotografía o el nombre en el encabezado del chat; mostrar intereses solo cuando la visibilidad pública esté activa.
- [ ] Si el usuario actual no tiene intereses, permitirle explorar grupos y buscarlos manualmente, pero no mostrar recomendaciones automáticas de personas ni grupos.

### B. Descubrimiento y administración de grupos

- [ ] Implementar recomendaciones de grupos descubribles con al menos un interés coincidente; ordenar por coincidencias y desempatar con el mismo cursor firmado y semilla que las personas.
- [ ] Excluir de recomendaciones los grupos en los que el usuario ya participa o que administra.
- [ ] Implementar búsqueda parcial por nombre que devuelva únicamente grupos descubribles, incluso cuando el usuario no tenga intereses configurados.
- [ ] Mostrar en los resultados públicos nombre, descripción, intereses, cantidad de integrantes y plazas disponibles; nunca mostrar miembros ni mensajes a usuarios externos.
- [ ] Al seleccionar una tarjeta de grupo, abrir una vista de información antes de mostrar `Solicitar unirse`.
- [ ] Mostrar `Grupo completo` cuando tenga diez integrantes y deshabilitar la solicitud.
- [ ] Permitir que únicamente el administrador actual active/desactive `Grupo descubrible` y modifique descripción/intereses.
- [ ] Al desactivar el descubrimiento, retirar el grupo inmediatamente de recomendaciones y búsquedas externas, conservar las membresías existentes y rechazar/notificar las solicitudes pendientes.

### C. Solicitudes de incorporación

- [ ] Implementar creación de solicitudes para grupos descubribles; compartir intereses no será requisito para solicitar ingreso.
- [ ] Permitir una sola solicitud pendiente global por usuario. Mientras exista una, el usuario podrá explorar, pero no solicitar otros grupos.
- [ ] No ofrecer acción para cancelar una solicitud pendiente.
- [ ] Implementar estados `pendiente`, `aceptada`, `rechazada` y `expirada`.
- [ ] Expirar automáticamente solicitudes sin respuesta después de 14 días y notificar al solicitante.
- [ ] Integrar la administración de solicitudes dentro de la información/configuración del grupo; no crear un panel global ni «Mis solicitudes».
- [ ] Mostrar al administrador foto, nombre, alias, intereses compartidos y fecha mediante `AdminJoinRequestItem`; no exponer el correo ni solicitar motivos de rechazo.
- [ ] Ordenar las solicitudes recibidas de la más antigua a la más reciente.
- [ ] Permitir al administrador aceptar o rechazar. Al aceptar, incorporar inmediatamente al usuario y crear su periodo de membresía.
- [ ] Si es la primera incorporación, permitirle ver solo mensajes posteriores a su entrada; si ya había pertenecido al grupo, recuperar únicamente los periodos históricos que correspondan.
- [ ] Aplicar siete días de espera solo después de un rechazo manual. Durante el plazo, el grupo sigue visible pero el botón de solicitud queda deshabilitado.
- [ ] Permitir volver a solicitar sin espera después de una salida voluntaria.
- [ ] Si el usuario es añadido directamente al grupo que tiene pendiente, resolver la solicitud como aceptada y crear una sola membresía.
- [ ] Si es añadido directamente a otro grupo, rechazar automáticamente su solicitud pendiente anterior.
- [ ] Si el grupo alcanza diez miembros antes de aceptar, impedir que se supere el límite y rechazar automáticamente la solicitud correspondiente; resolver de forma transaccional las aceptaciones concurrentes. La aceptación en un grupo completo responde `200` con la solicitud `rejected`, motivo `group_full` y `membership: null`; el `409 group_full` corresponde a crear la solicitud.
- [ ] Si cambia el administrador, conservar solicitudes pendientes para que el nuevo administrador pueda gestionarlas.
- [ ] Probar que los rechazos automáticos (grupo completo, grupo privado o incorporación directa a otro grupo) no apliquen la espera de siete días.

### D. Auditoría, RLS e integridad

- [ ] Crear `registros_auditoria` con actor, acción, entidad, ID, fecha, valores anteriores/nuevos cuando corresponda.
- [ ] Registrar operaciones críticas: mensajes, versiones, eliminaciones, encuestas, votos, membresías, administración, perfiles, intereses, publicación de grupos y solicitudes.
- [ ] Hacer que las operaciones normales solo puedan insertar registros de auditoría; no permitir editar/borrar desde la aplicación.
- [ ] Verificar que mensajes eliminados no aparezcan en consultas normales ni respuestas de API.
- [ ] Revisar todas las políticas RLS de tablas expuestas, incluyendo catálogo/intereses, relaciones de intereses, perfiles públicos, grupos descubribles y solicitudes.
- [ ] Comprobar políticas para miembros activos, antiguos miembros, expulsados, reincorporados y usuarios ajenos.
- [ ] Asegurar que las personas externas solo puedan leer los campos públicos de perfiles/grupos y nunca la lista de integrantes, mensajes, correo ni solicitudes ajenas.
- [ ] Asegurar que solo el dueño edite sus intereses/visibilidad personal y solo el administrador actual gestione publicación, intereses, descripción y solicitudes del grupo.
- [ ] Comprobar que `contactos_usuario` no sea accesible desde el navegador.
- [ ] Revisar que el rol SQLAlchemy no pueda saltarse RLS.
- [ ] Probar el contexto local por transacción y ausencia de fugas en el pool.
- [ ] Probar permisos de Storage y Realtime, incluidos canales privados de notificaciones sociales.
- [ ] Añadir índices a claves foráneas, búsquedas, filtros de membresía, coincidencias de intereses y orden de mensajes/solicitudes.
- [ ] Revisar restricciones únicas y checks para conversaciones, miembros, alias, votos, reacciones, límites de intereses y solicitudes.
- [ ] Ejecutar revisión de seguridad y rendimiento de Supabase; corregir alertas relevantes.
- [ ] Crear pruebas negativas: intentar acceder a conversaciones ajenas, cambiar autor, votar duplicado, editar mensaje ajeno, consultar correo privado, solicitar dos grupos a la vez, gestionar solicitudes ajenas o publicar grupos sin permisos.
- [ ] Aplicar los límites de frecuencia de Descubrir (30/min), creación de solicitudes (10/min) y consulta de la propia (60/min).
- [ ] Implementar `app.publish_social_event(...)` y `app.expire_pending_join_requests()`; programar el job de `pg_cron` cada 15 min como `chatly_app`.
- [ ] Revocar `authenticated` de `chatly_app` y validar que `app.current_actor_id()` `SECURITY DEFINER` resuelve `auth.uid()`.
- [ ] Verificar el cursor firmado y el rechazo de cursores alterados.

### Entregables

- Sección Descubrir para personas y grupos.
- Recomendaciones y búsqueda por intereses.
- Publicación y administración de grupos descubribles.
- Flujo completo de solicitudes de unión.
- Auditoría operativa y matriz de permisos actualizada.
- Políticas RLS y eventos Realtime revisados.
- Pruebas funcionales, de autorización e integridad social.

### Criterios de salida

- Las personas y grupos recomendados cumplen exactamente los filtros y el orden acordados.
- La visibilidad pública del perfil y de los grupos es independiente.
- Una persona externa no puede consultar miembros ni mensajes de un grupo descubrible.
- Un usuario no puede mantener dos solicitudes pendientes ni superar los límites del grupo.
- Los periodos de espera y la caducidad se aplican correctamente.
- Las notificaciones solo llegan al administrador correspondiente o al solicitante de la solicitud.
- No hay rutas conocidas que permitan saltarse las reglas de membresía, visibilidad o autorización.

## Iteración 9 — Fotografías, correo y datos de demostración

**Fechas:** 1–14 de marzo de 2027  
**Objetivo:** completar los servicios externos necesarios y preparar una demo con contenido realista, incluyendo datos suficientes para demostrar Descubrir.

### Tareas

- [ ] Crear bucket privado `avatars` en Supabase Storage.
- [ ] Implementar políticas para que el usuario suba/cambie su propio avatar y los usuarios autorizados consulten fotografías.
- [ ] Validar formatos JPEG/PNG/WebP y límite de 2 MB en backend.
- [ ] Generar URLs firmadas de duración limitada para mostrar fotografías.
- [ ] Conservar archivos anteriores y actualizar solo la referencia vigente del perfil.
- [ ] Implementar avatar predeterminado y avatares generados para grupos.
- [ ] Finalizar configuración de SMTP personalizado en Supabase Auth.
- [ ] Probar confirmación, reenvío y recuperación con cuentas externas al equipo.
- [ ] Revisar capacidad y límites vigentes del plan gratuito de correo; registrar una alternativa si el proveedor cambia condiciones.
- [ ] Crear script idempotente de seed para cinco cuentas verificadas y datos de demostración.
- [ ] Preparar conversaciones privadas, grupos, mensajes, reacciones y encuestas con resultados.
- [ ] Preparar intereses distribuidos entre las cinco cuentas para demostrar coincidencias distintas y empates en recomendaciones.
- [ ] Preparar grupos descubribles con descripciones/intereses, grupos privados que no deben aparecer y al menos un grupo completo para validar su estado.
- [ ] Preparar solicitudes de demostración en estados pendientes, aceptados, rechazados y expirados, sin violar la regla de una solicitud pendiente por usuario.
- [ ] Documentar cómo se restablece/recrea el conjunto de datos demo sin duplicados.
- [ ] No guardar contraseñas reales ni secretos de cuentas demo en el repositorio.

### Entregables

- Storage privado integrado.
- Correos de Auth comprobados.
- Cinco cuentas y datos de demostración reproducibles para mensajería y descubrimiento social.

### Criterios de salida

- Las fotografías no son accesibles públicamente sin autorización/enlace firmado.
- Un usuario no puede reemplazar el avatar de otra persona.
- El registro con correo real y la recuperación funcionan.
- La base demo se puede preparar de forma repetible.
- Las recomendaciones de personas/grupos y las solicitudes pueden demostrarse con las cuentas y datos precargados.

## Iteración 10 — PWA y modo offline

**Fechas:** 15–28 de marzo de 2027  
**Objetivo:** ofrecer el alcance offline acordado sin intentar convertir la aplicación en una app totalmente offline.

### Tareas

- [ ] Preparar manifest, nombre Chatly, iconos, colores e instalación PWA.
- [ ] Implementar Service Worker para shell estático y recursos necesarios.
- [ ] Diseñar esquema IndexedDB para conversaciones, últimos 50 mensajes por conversación, borradores y outbox.
- [ ] Persistir los últimos 50 mensajes recibidos por conversación.
- [ ] Mostrar encuestas en modo lectura con los últimos resultados almacenados.
- [ ] Deshabilitar votos, reacciones y acciones que requieran servidor mientras no haya conexión.
- [ ] Implementar redacción y cola local de mensajes de texto.
- [ ] Asignar UUID/idempotency key a cada mensaje pendiente.
- [ ] Implementar estados pendiente, enviando, enviado y fallido.
- [ ] Reintentar al detectar reconexión o al volver a abrir la aplicación.
- [ ] Validar permisos al sincronizar; si el usuario salió/fue expulsado o el grupo se archivó, marcar el mensaje fallido y conservar el texto para informar al usuario.
- [ ] Resolver orden de envío y reintentos sin duplicados.
- [ ] Al cerrar sesión, advertir sobre mensajes pendientes; permitir esperar o descartarlos explícitamente y limpiar caché/datos de sesión.
- [ ] Probar instalación, actualización de Service Worker, desconexión, reconexión y limpieza de datos en navegadores de escritorio y móviles.

> **Límite de alcance:** no añadir cola offline para solicitudes de unión, edición de intereses ni cambios de visibilidad. Las funciones sociales se usarán conectadas al servidor; no se amplía el modo offline acordado.

### Entregables

- PWA instalable.
- Caché offline acordada.
- Cola de mensajes pendientes.
- Pruebas de sincronización e idempotencia.

### Criterios de salida

- La aplicación abre y muestra contenido previamente almacenado sin conexión.
- No permite votar ni modificar datos remotos offline.
- Los mensajes pendientes se sincronizan al volver la conexión sin duplicarse.
- Si el servidor rechaza un mensaje, el usuario ve el estado fallido y no pierde silenciosamente el texto.
- El cierre de sesión limpia los datos locales según la regla acordada.

## Iteración 11 — Integración completa y congelación funcional

**Fechas:** 29 de marzo–11 de abril de 2027  
**Objetivo:** probar los flujos completos entre todos los módulos y dejar de añadir funcionalidades.

### Tareas

- [ ] Integrar autenticación, perfiles, intereses, búsqueda, Descubrir, chats, grupos, solicitudes, mensajes, encuestas, Realtime, Storage y offline.
- [ ] Ejecutar pruebas end-to-end con al menos cinco usuarios/sesiones.
- [ ] Probar un registro con intereses omitidos y la posterior configuración de intereses en el perfil.
- [ ] Probar recomendaciones de personas: coincidencia mínima, orden por coincidencias, empates aleatorios, exclusión de chats existentes y filtros de visibilidad.
- [ ] Probar que personas que comparten grupo, pero no tienen conversación privada, puedan aparecer como recomendación.
- [ ] Probar que seleccionar una persona abra el chat y que la conversación solo se cree al enviar el primer mensaje.
- [ ] Probar publicación de grupo privado a descubrible, búsqueda parcial, vista de información y retirada inmediata al volverlo privado.
- [ ] Probar solicitudes: una pendiente global, rechazo manual y espera de siete días, expiración a los 14 días, aceptación inmediata y ausencia de cancelación/«Mis solicitudes».
- [ ] Probar casos de solicitud automática: grupo completo, grupo privado, usuario añadido directamente al mismo grupo y usuario añadido directamente a otro grupo.
- [ ] Probar cambio de administrador con solicitudes pendientes y concurrencia al alcanzar el máximo de diez integrantes.
- [ ] Probar notificaciones de llegada y resolución de solicitudes.
- [ ] Probar un chat privado completo de inicio a cierre.
- [ ] Probar un grupo completo: crear, añadir, expulsar, salir, sucesión de admin, ocultar y archivar.
- [ ] Probar historial de usuario expulsado/reincorporado y permisos por periodo.
- [ ] Probar encuesta desde creación hasta cierre, cambio de voto y creador que abandona el grupo.
- [ ] Probar edición, borrado lógico, respuestas a mensajes eliminados y auditoría.
- [ ] Probar presencia, escritura, confirmaciones y notificaciones internas.
- [ ] Probar offline/reconexión y salida de sesión con mensajes pendientes.
- [ ] Corregir inconsistencias de interfaz, estados de carga, errores y mensajes en español.
- [ ] Revisar responsive en tamaños de escritorio y móvil.
- [ ] Realizar pruebas básicas de accesibilidad y navegación con teclado.
- [ ] Medir tiempos de carga y consultas evidentes; corregir problemas relevantes para cinco usuarios.
- [ ] Congelar el alcance funcional al finalizar la iteración. Solo se aceptarán correcciones, no nuevas funcionalidades.

### Entregables

- Candidato funcional completo.
- Informe de pruebas end-to-end de mensajería y descubrimiento social.
- Lista priorizada de defectos pendientes.
- Alcance funcional congelado.

### Criterios de salida

- Todos los flujos críticos tienen pruebas reproducibles.
- No quedan defectos bloqueantes o de seguridad conocidos sin plan de resolución.
- Los cuatro integrantes pueden levantar y probar la aplicación desde una copia limpia del repositorio.

## Iteración 12 — Despliegue, documentación y ensayo

**Fechas:** 12–25 de abril de 2027  
**Objetivo:** desplegar una versión candidata y preparar la demostración pública.

### Tareas

- [ ] Preparar configuración de Render Free para ejecutar Reflex y su backend integrado.
- [ ] Configurar variables de entorno y secretos en el panel de Render.
- [ ] Configurar Supabase Auth: URL pública, redirect URLs, SMTP, expiración de JWT y límites.
- [ ] Configurar Session Pooler, SSL y parámetros de conexión adecuados para el servicio desplegado.
- [ ] Ejecutar migraciones Alembic en el entorno de demo mediante un procedimiento controlado.
- [ ] Aplicar políticas RLS, publicación Realtime y políticas de Storage, incluyendo los recursos sociales.
- [ ] Ejecutar `0014_social_cron` y verificar la extensión `pg_cron`, el job de expiración y `app.publish_social_event` en el entorno desplegado.
- [ ] Ejecutar seed de cinco cuentas y contenido de demostración de mensajería, intereses, perfiles públicos/privados, grupos descubribles y solicitudes.
- [ ] Probar registro real, confirmación y recuperación desde la URL pública.
- [ ] Probar mensajes y encuestas entre usuarios en navegadores/dispositivos distintos.
- [ ] Probar descubrimiento de personas y grupos, publicación/privacidad y solicitudes desde la URL pública.
- [ ] Probar PWA desde la URL desplegada.
- [ ] Probar restauración cuando Render haya estado inactivo y documentar el tiempo de arranque.
- [ ] Revisar la política de pausa por inactividad del plan gratuito de Supabase y el estado del proyecto antes de la presentación.
- [ ] Verificar límites gratuitos vigentes de Render, Supabase y Brevo; no asumir que las cuotas permanecen iguales.
- [ ] Crear guía de usuario y guía de instalación/desarrollo.
- [ ] Completar diagramas de arquitectura, modelo de datos y flujos principales, incluyendo el flujo social.
- [ ] Actualizar documentación técnica: decisiones funcionales Q1–Q179, contratos de API, esquema de base de datos, matriz de autorización, eventos Realtime y despliegue.
- [ ] Preparar guion de demostración que cubra mensajería, encuestas, descubrimiento de personas, descubrimiento de grupos y solicitud de incorporación.
- [ ] Realizar al menos dos ensayos completos con el equipo.

### Entregables

- URL pública candidata.
- Entorno Supabase configurado.
- Documentación técnica y de usuario actualizada.
- Guion de demostración social y de mensajería.
- Lista final de defectos no bloqueantes.

### Criterios de salida

- El despliegue puede reconstruirse desde el repositorio.
- Las variables secretas no están versionadas.
- La aplicación funciona con cinco usuarios de prueba.
- Los registros con correo real y los flujos principales, incluidas las funciones sociales, funcionan desde la URL pública.
- Se conocen y aceptan las pausas/limitaciones de los servicios gratuitos.

## Fase final — Entrega y demostración

**Fechas:** 26–30 de abril de 2027  
**Objetivo:** estabilizar y presentar la versión final.

### Tareas

- [ ] Congelar código y dependencias; no añadir funcionalidades.
- [ ] Corregir únicamente defectos críticos y de alta prioridad.
- [ ] Ejecutar la suite completa de pruebas.
- [ ] Verificar migraciones y estado de Supabase.
- [ ] Comprobar que las cinco cuentas demo funcionan y que sus credenciales están disponibles para el equipo/evaluadores de forma segura.
- [ ] Preparar un plan alternativo de presentación si Render o Supabase Free están pausados o indisponibles.
- [ ] Crear tag de versión, por ejemplo `v1.0.0-demo`.
- [ ] Publicar README final, instrucciones de uso y limitaciones conocidas.
- [ ] Realizar demostración final antes del 30 de abril.

### Entregable final

**Chatly V1 desplegado y demostrable antes del 30 de abril de 2027**, acompañado de repositorio, documentación, modelo de datos, pruebas y guion de presentación. La demostración incluirá la experiencia social por intereses compartidos.

---

# 6. Distribución sugerida del trabajo entre cuatro integrantes

Los nombres se dejan como Integrante A–D porque aún no se han indicado. La asignación es de **responsabilidad principal**, no una separación rígida: las funcionalidades se integran mediante PR y revisión cruzada.


| Integrante                               | Responsabilidad principal                                    | Tareas habituales                                                                                                                                                   |
| ---------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A — Backend y datos**                  | Persistencia, esquema y seguridad de base de datos           | SQLAlchemy, Psycopg, Alembic, modelos, constraints, índices, transacciones, RLS, contexto de usuario, auditoría e integridad de relaciones de intereses/solicitudes |
| **B — Servicios y reglas de negocio**    | Casos de uso y API                                           | Auth backend, perfiles, intereses, búsqueda, recomendaciones, conversaciones, membresías, solicitudes de unión, mensajes, encuestas y validaciones                  |
| **C — Frontend Reflex**                  | Interfaz y experiencia de usuario                            | Páginas, componentes, layouts, estados Reflex, formularios, chat, grupos, Descubrir, perfiles, selección de intereses, solicitudes, encuestas, responsive y español |
| **D — Integraciones, offline y calidad** | Cliente Realtime, PWA y automatización de pruebas/despliegue | Supabase JS, Postgres Changes, Presence, Broadcast, notificaciones sociales, IndexedDB, Service Worker, pruebas E2E y Render                                        |


## Reglas de colaboración

- Cada funcionalidad debe tener un responsable principal y al menos un revisor de otro integrante.
- Las migraciones deben revisarse por A y B antes de integrarse.
- Las políticas RLS y cambios de autorización requieren revisión de A y B.
- Las integraciones de Realtime deben revisarse junto con el contrato del evento y la política RLS correspondiente.
- D no será el único responsable de probar: cada autor debe añadir pruebas de su funcionalidad.
- C y B deben acordar contratos de API/servicios antes de construir pantallas dependientes.
- Integrar cambios pequeños y frecuentemente; evitar ramas largas con muchos conflictos.
- Mantener revisiones cruzadas en PR y ejecutar localmente Ruff y pytest; no asumir que existe CI/CD obligatorio en GitHub, ya que fue descartado en la preparación del proyecto.

## Reparto por etapa


| Etapa                      | A                                                             | B                                                 | C                                                                 | D                                            |
| -------------------------- | ------------------------------------------------------------- | ------------------------------------------------- | ----------------------------------------------------------------- | -------------------------------------------- |
| Setup y arquitectura       | DB/CI y configuración                                         | servicios base/API                                | shell Reflex y diseño UI                                          | automatización y entorno de prueba           |
| Auth, perfiles e intereses | tablas/RLS de perfiles e intereses                            | Auth, perfiles, catálogo y servicios de intereses | pantallas Auth/perfil y selector por categorías                   | pruebas Auth, SMTP y privacidad              |
| Conversaciones/grupos      | relaciones y restricciones, grupos descubribles y solicitudes | reglas de grupos/membresía y ciclo de solicitudes | lista, chat y gestión de grupo                                    | pruebas de casos límite                      |
| Mensajería                 | mensajes/versiones/lecturas                                   | servicios de mensajes y reacciones                | interfaz de chat                                                  | contratos y pruebas de integración           |
| Realtime                   | publicación/RLS                                               | eventos de dominio y notificaciones               | actualización de estados UI                                       | cliente JS, Presence, Broadcast y reconexión |
| Encuestas                  | tablas y constraints                                          | reglas de voto/cierre                             | cards y resultados                                                | pruebas concurrentes y Realtime              |
| Descubrimiento social      | RLS, índices y consistencia                                   | endpoints, recomendaciones y solicitudes          | pantallas Personas/Grupos, perfil y administración de solicitudes | eventos, pruebas E2E y reconexión            |
| Auditoría/seguridad        | RLS, índices y auditoría                                      | autorización de servicios                         | estados de error/permisos                                         | pruebas negativas y revisión integral        |
| Storage/offline            | metadatos y acceso                                            | servicios de archivos                             | UI y estados offline                                              | Storage JS, SW, IndexedDB y sincronización   |
| Entrega                    | migraciones/DB                                                | API y reglas finales                              | pulido visual                                                     | despliegue, pruebas E2E y guion demo         |


---

# 7. Gestión del trabajo

## Cadencia recomendada

- **Inicio de iteración:** revisar objetivo, dividir tareas y asignar responsables.
- **Dos sincronizaciones breves por semana:** revisar avances y bloqueos.
- **Fin de iteración:** demo interna, revisión de criterios y retrospectiva.
- **Integración:** PR hacia `develop` y revisión cruzada; los checks locales de calidad siguen siendo obligatorios.
- **Cada cambio de BD:** migración Alembic y pruebas asociadas.

## Convención de ramas

```text
main
└── develop
    ├── feature/auth-email-verification
    ├── feature/profile-and-alias-search
    ├── feature/user-interests
    ├── feature/group-discovery
    ├── feature/join-requests
    ├── feature/chat-messaging
    ├── feature/poll-voting
    ├── feature/realtime-presence
    ├── feature/offline-outbox
    └── fix/...
```

## Convención de commits

Usar Conventional Commits:

```text
feat: add private conversation creation
feat: add interest-based discovery
feat: add group join requests
fix: prevent duplicate poll votes
chore: configure ruff and pytest
refactor: isolate message service
test: cover group membership history
docs: update social discovery contracts
```

## Definition of Done (DoD)

Una tarea no se considera terminada hasta que:

- Cumple sus criterios de aceptación.
- Incluye pruebas apropiadas (unitarias, integración o end-to-end según corresponda).
- Pasa `ruff check`, formato y pytest localmente.
- Respeta autorización, RLS y reglas de membresía aplicables.
- Maneja errores y estados de carga/vacío.
- No introduce secretos ni datos privados en logs.
- Actualiza documentación cuando cambia un contrato, configuración o flujo.
- Ha sido revisada e integrada en `develop`.

---

# 8. Criterios globales de aceptación de la V1

## Identidad, perfiles e intereses

- [ ] Un usuario puede registrarse, confirmar correo, iniciar sesión y recuperar contraseña.
- [ ] Un usuario no verificado no puede usar chats ni Descubrir.
- [ ] Alias único, formato válido y cambio limitado a una vez cada 30 días.
- [ ] Búsqueda parcial por alias y exacta por correo sin revelar el correo.
- [ ] El usuario puede omitir intereses en el registro y editarlos luego desde el perfil.
- [ ] Existe un catálogo administrado por la aplicación, organizado por categorías e intereses concretos.
- [ ] Cada usuario puede seleccionar como máximo diez intereses.
- [ ] La visibilidad pública del perfil está activada por defecto y puede desactivarse.
- [ ] Con visibilidad desactivada, el usuario no aparece en sugerencias y sus intereses quedan ocultos, pero continúa siendo localizable mediante búsqueda directa.

## Descubrimiento de personas

- [ ] Solo se recomiendan personas con visibilidad pública activa, intereses configurados y al menos una coincidencia.
- [ ] Más intereses coincidentes aparecen primero; los empates se aleatorizan.
- [ ] Las recomendaciones se actualizan al abrir/actualizar Descubrir.
- [ ] Se excluyen usuarios con quienes ya existe un chat privado; se permiten personas que comparten grupos si aún no tienen chat privado.
- [ ] La tarjeta muestra fotografía, nombre, intereses compartidos y estado online cuando esté disponible; no muestra alias ni contador adicional.
- [ ] Al seleccionar la tarjeta se abre el chat; la conversación se crea solo al enviar el primer mensaje.
- [ ] Se muestran 20 resultados y se pueden cargar otros 20.
- [ ] El catálogo de intereses responde sin sesión; el resto de Descubrir exige usuario verificado.
- [ ] El cursor es firmado y conserva la semilla; un cursor alterado se rechaza.
- [ ] Los límites de frecuencia 30/10/60 se aplican.
- [ ] El estado `online` no viene del DTO REST; se obtiene por Presence.

## Descubrimiento de grupos y solicitudes

- [ ] Los grupos son privados por defecto y solo su administrador puede hacerlos descubribles.
- [ ] Un grupo descubrible tiene descripción de 10–300 caracteres y entre uno y cinco intereses asociados.
- [ ] La información externa no expone miembros ni mensajes.
- [ ] Se recomiendan grupos con al menos una coincidencia; se excluyen grupos donde el usuario participa o que administra.
- [ ] La búsqueda parcial por nombre solo muestra grupos descubribles.
- [ ] Los grupos completos permanecen visibles, pero no aceptan nuevas solicitudes.
- [ ] Desactivar el descubrimiento elimina al grupo de resultados externos y resuelve sus solicitudes pendientes automáticamente.
- [ ] El usuario puede solicitar unirse sin compartir intereses, pero solo puede tener una solicitud pendiente global.
- [ ] No puede cancelar una solicitud; esta expira a los 14 días si no hay respuesta.
- [ ] El administrador gestiona solicitudes desde la información/configuración del grupo, ordenadas de más antiguas a más recientes.
- [ ] El administrador ve foto, nombre, alias, intereses compartidos y fecha; no ve correo ni solicita motivo de rechazo.
- [ ] Aceptar incorpora inmediatamente al usuario y respeta el historial de membresías.
- [ ] El rechazo manual establece siete días de espera; los rechazos automáticos no.
- [ ] El límite de diez integrantes se respeta incluso con aceptaciones concurrentes.
- [ ] Los cambios de administrador preservan solicitudes pendientes.
- [ ] No existe sección «Mis solicitudes».
- [ ] Aceptar una solicitud en un grupo completo devuelve `200` con `rejected` y `membership: null`; el `409` corresponde a crear la solicitud.
- [ ] La caducidad la ejecuta `pg_cron` y publica `join_request.resolved`.
- [ ] El administrador recibe `AdminJoinRequestItem` con foto, nombre, alias, intereses compartidos y fecha.

## Relaciones entre usuarios

- [ ] No existe sistema de amistades, seguidores ni solicitudes de contacto.
- [ ] No hay solicitudes para iniciar una conversación privada.
- [ ] No se implementan bloqueo, reportes ni moderación avanzada en V1.

## Conversaciones y grupos

- [ ] Una conversación privada única por pareja.
- [ ] Grupo de 3–10 integrantes al crearse.
- [ ] Administración única y sucesión automática.
- [ ] Incorporación, expulsión, salida y reincorporación respetan periodos de membresía.
- [ ] «Salir» conserva historial en lectura; «Salir y eliminar» oculta individualmente.
- [ ] Última salida archiva el grupo definitivamente.
- [ ] Los usuarios solo consultan los periodos en que pertenecieron al grupo.

## Mensajería

- [ ] Envío y recepción de texto, límite 4.000 caracteres.
- [ ] Respuestas, edición, etiqueta «editado», versiones y eliminación lógica.
- [ ] Reacciones con los siete emojis y una reacción vigente por usuario/mensaje.
- [ ] Paginación de 50 iniciales y 30 por carga anterior.
- [ ] Mensajes de sistema en historial y lectura.
- [ ] ✓ al guardar en servidor y ✓✓ según participantes elegibles.

## Encuestas

- [ ] Pregunta 5–200 caracteres, 2–5 opciones de 1–80 caracteres.
- [ ] Edición permitida solo por el creador antes del primer voto.
- [ ] Un voto vigente por usuario, cambio permitido mientras esté abierta.
- [ ] Resultados y votantes visibles/actualizados.
- [ ] Cierre definitivo por creador o administrador en el caso acordado.
- [ ] El archivo del grupo cierra encuestas pendientes.

## Tiempo real y offline

- [ ] Postgres Changes actualiza a participantes autorizados.
- [ ] Presence representa sesiones online.
- [ ] Broadcast muestra «escribiendo…» y expira en cinco segundos.
- [ ] Notificaciones sociales privadas para solicitudes recibidas y resueltas.
- [ ] Caché de últimos 50 mensajes por conversación.
- [ ] Cola de texto offline con idempotencia y reintentos.
- [ ] Al cerrar sesión se advierte sobre pendientes y se limpia la caché.

## Auditoría y seguridad

- [ ] Operaciones críticas registradas con actor, acción, entidad, fecha y valores anteriores/nuevos cuando corresponda.
- [ ] Los borrados funcionales son lógicos.
- [ ] RLS protege las tablas y eventos según autorización.
- [ ] El backend verifica JWT y deriva la identidad del token.
- [ ] `contactos_usuario` no es público.
- [ ] Los datos de perfiles y grupos expuestos en Descubrir se limitan a los campos públicos aprobados.
- [ ] Las solicitudes y notificaciones solo son visibles para el solicitante y el administrador correspondiente.
- [ ] Bucket de avatares privado y archivos accesibles solo con autorización.
- [ ] Las pruebas negativas impiden accesos cruzados y modificaciones ajenas.
- [ ] `chatly_app` no hereda `authenticated`; `app.current_actor_id()` es `SECURITY DEFINER` y `EXECUTE` se limita a los roles necesarios.

## Entrega

- [ ] URL pública gratuita.
- [ ] Cinco cuentas de demostración y datos precargados para mensajería y descubrimiento.
- [ ] Registro de usuarios reales probado.
- [ ] Pruebas de los flujos principales y sociales completadas.
- [ ] README, guía de uso, arquitectura y modelo de datos publicados.
- [ ] Demostración ensayada.

---

# 9. Riesgos principales y medidas de mitigación


| Riesgo                                       | Impacto                                                                                                                                            | Mitigación / decisión de planificación                                                                                                                                                 |
| -------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| RLS con conexión SQLAlchemy directa          | Alto: puede exponer datos si el contexto no se establece correctamente                                                                             | Hacer una prueba técnica en Iteración 1; usar contexto local por transacción, rol sin `BYPASSRLS` y tests de fuga entre conexiones.                                                    |
| Autorización de Realtime tras expulsión      | Alto: un antiguo miembro podría mantener una suscripción existente temporalmente                                                                   | Desuscribir en cliente, validar acceso en RLS/Realtime, refrescar JWT y probar conexiones persistentes. Documentar que la revocación no es instantánea para un cliente que no coopera. |
| Offline e idempotencia                       | Alto: mensajes duplicados o pérdida de mensajes                                                                                                    | Implementar UUID por mensaje, outbox, estados explícitos y pruebas de reconexión antes de ampliar el offline.                                                                          |
| Complejidad de membresías históricas         | Alto: historial visible incorrectamente                                                                                                            | Modelar periodos desde Iteración 3; no reducir membresía a un booleano `is_member`.                                                                                                    |
| Borrado lógico y auditoría                   | Medio/alto: el contenido eliminado podría filtrarse por una consulta secundaria                                                                    | Centralizar serialización/consultas, separar historial y contenido visible, añadir pruebas negativas.                                                                                  |
| Solicitudes globales y límite de integrantes | Alto: dos solicitudes podrían aceptarse simultáneamente y superar el máximo de diez integrantes o dejar más de una solicitud pendiente por usuario | Resolver aceptación, incorporación directa y cierre de solicitudes en transacciones; bloquear/validar el estado del usuario y del grupo; probar concurrencia.                          |
| Privacidad de descubrimiento                 | Alto: perfiles, grupos, miembros o mensajes podrían mostrarse a usuarios no autorizados                                                            | Aplicar visibilidad por separado para perfil y grupo; limitar DTOs públicos; probar RLS, endpoints y canales Realtime.                                                                 |
| Recomendaciones de intereses                 | Medio: resultados inconsistentes o demasiado amplios                                                                                               | Usar catálogo controlado, máximo de diez intereses por usuario y cinco por grupo; exigir al menos una coincidencia y probar filtros/exclusiones.                                       |
| Correo de confirmación                       | Medio: límites del SMTP predeterminado o del plan gratuito                                                                                         | Configurar SMTP externo temprano, probar correos reales y verificar cuotas vigentes antes de la demo.                                                                                  |
| Servicios gratuitos                          | Alto para la presentación: pausa o arranque lento                                                                                                  | Ensayar el despliegue antes de presentar y comprobar Supabase/Render con antelación. Mantener un plan de demostración local.                                                           |
| Alcance extenso para seis meses              | Alto: retraso de funciones críticas                                                                                                                | No añadir funcionalidades fuera de las 179 decisiones aprobadas; congelar funcionalidades el 11 de abril. Priorizar flujos verticales completos.                                       |
| PWA en Reflex                                | Medio/alto: integración del Service Worker puede requerir JS específico                                                                            | Hacer una prueba de instalación y caché básica antes de la fase offline; mantener offline acotado a lectura y cola de mensajes de texto.                                               |
| Enumeración de Descubrir                     | Medio: un usuario podría recorrer toda la población pública verificada                                                                             | Aplicar los límites de frecuencia (30/min) y el cursor firmado; medir con cinco cuentas.                                                                                                |
| Herencia de roles                            | Alto: `chatly_app` podría conservar privilegios de `authenticated`                                                                                 | Revocar `authenticated`, dejar `noinherit`, usar `app.current_actor_id()` `SECURITY DEFINER` y revisar con `supabase db advisors`.                                                      |


## Limitaciones de los planes gratuitos que deben asumirse

- Render Free puede suspender el servicio web tras 15 minutos sin tráfico entrante y el siguiente arranque puede tardar alrededor de un minuto. Su sistema de archivos es efímero: no almacenar allí imágenes ni datos persistentes. [Documentación de Render Free](https://render.com/docs/free).
- Supabase Free puede pausar proyectos con poca actividad durante una semana. Revisar el estado del proyecto y realizar pruebas con anticipación a la demostración. [Documentación de pausa de proyectos](https://supabase.com/docs/guides/platform/free-project-pausing).
- Los límites, cuotas, restricciones de correo y condiciones de los planes pueden cambiar. Verificarlos de nuevo durante Iteraciones 9 y 12; no asumir que las cifras actuales seguirán vigentes en abril de 2027.

---

# 10. Plan de contingencia si el calendario se retrasa

No se deben eliminar las reglas de seguridad o integridad para recuperar tiempo. Si hay retrasos, reducir primero el refinamiento, no los controles críticos.

### No recortar

- Registro y confirmación de correo.
- Chats privados y grupales.
- Mensajes persistidos.
- Encuestas y votos consistentes.
- Autorización por usuario y conversación.
- Historial de membresías.
- Borrado lógico y auditoría de operaciones críticas.
- Reglas esenciales de descubrimiento por intereses y privacidad.
- Solicitudes con límite global, caducidad y límite de integrantes.
- Pruebas de autorización.
- Despliegue y cinco cuentas de demostración.

### Simplificar primero

1. Pulido visual no esencial y animaciones.
2. Cobertura offline a exactamente los últimos 50 mensajes y solo cola de texto (sin extenderla a otras acciones).
3. Afinar notificaciones visuales; mantener el contador de no leídos y las notificaciones básicas de solicitudes.
4. Refinar reportes y gráficos de pruebas, manteniendo el conjunto mínimo de pruebas de seguridad e integridad.
5. Reducir el número de datos ficticios adicionales; conservar cinco cuentas y escenarios suficientes para la demo.

No añadir llamadas, adjuntos, push, sonidos, encuestas anónimas, bots, amistades, seguidores, bloqueo, reportes ni otras funciones excluidas.

---

# 11. Documentación que debe quedar en `docs/`

- `docs/chatly.md` — las 179 decisiones funcionales aprobadas (Q1–Q179), con reglas finales y trazabilidad.
- `docs/architecture.md` — contexto, componentes, responsabilidades y diagramas.
- `docs/database-schema.md` — entidades, campos, relaciones, restricciones e índices, incluidos intereses y solicitudes.
- `docs/authorization-matrix.md` — permisos por usuario, rol, visibilidad y periodo de membresía.
- `docs/realtime-events.md` — canales, eventos, payloads, autorización y ciclo de vida, incluidos eventos sociales privados.

- `docs/api-contracts.md` — endpoints, validación, errores y autenticación, incluidos perfiles/intereses/Descubrir/solicitudes.

---

# 12. Definición final de éxito

Chatly V1 se considerará terminada cuando, antes del **30 de abril de 2027**, el equipo pueda desplegar y demostrar en una URL pública gratuita, con cinco cuentas de prueba y registro real, una aplicación web en español que permita conversar en privado y en grupos, gestionar membresías con historial, enviar mensajes en tiempo real, reaccionar y responder, editar/eliminar con trazabilidad, crear y votar encuestas, mostrar presencia y lectura, descubrir personas y grupos mediante intereses compartidos, gestionar solicitudes de incorporación y consultar/enviar mensajes básicos con el comportamiento offline definido.

El propósito no es competir con WhatsApp en amplitud, sino demostrar una implementación coherente y verificable de un conjunto delimitado de funcionalidades de mensajería, toma de decisiones y descubrimiento social. No se añadirá un sistema de amistades ni funcionalidades sociales adicionales fuera de las 179 decisiones aprobadas.