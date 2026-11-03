# Chatly — Roadmap de desarrollo

> **Nombre vigente:** Chatly     
> **Plataforma:** aplicación web responsive e instalable como PWA.  
> **Idioma de la V1:** español.

Este roadmap convierte las decisiones funcionales aprobadas durante Grill Me (Q1–Q108) en un plan de trabajo. Las reglas de producto se consideran acordadas; los detalles de implementación —campos, índices, restricciones, políticas RLS y contratos de API— se concretarán en las tareas de diseño técnico indicadas aquí.

---

## 1. Visión y objetivo de entrega

**Chatly** será una aplicación de mensajería inspirada en WhatsApp, con conversaciones privadas y grupales y encuestas/votaciones integradas en los chats. La V1 debe demostrar que el equipo puede implementar lógica de negocio, autenticación, autorización, persistencia, comunicación en tiempo real, trazabilidad y sincronización offline básica.

La entrega se considerará lista cuando exista una URL pública gratuita con:

- Cinco cuentas de demostración preparadas y datos iniciales para que la aplicación no esté vacía.
- Registro de nuevos usuarios con correo real y confirmación obligatoria.
- Conversaciones privadas y grupales funcionales.
- Mensajería, reacciones, respuestas, edición, eliminación lógica y confirmaciones de lectura.
- Encuestas con votación, resultados en tiempo real y cierre.
- Presencia y estado de escritura.
- Historial y permisos coherentes con los periodos de membresía.
- Auditoría de operaciones importantes.
- PWA instalable y modo offline limitado a la experiencia acordada.
- Pruebas de aceptación superadas y documentación de entrega.

No se exige soportar miles de usuarios, ofrecer SLA ni operar como servicio comercial.

## 2. Supuestos de planificación

- **Ramas:** `main` para versiones estables, `develop` para integración y ramas `feature/*` para trabajo funcional.
- **Base de datos:** Supabase PostgreSQL en la nube. Alembic administra el esquema propio de Chatly; no se duplicarán las migraciones de esas tablas mediante Supabase CLI.
- **Conexión PostgreSQL:** Session Pooler de Supabase para desarrollo y Render, sujeto a validar la configuración del proyecto. La aplicación utilizará una conexión con privilegios mínimos.
- **Backend:** Reflex como framework full-stack, con endpoints FastAPI integrados. No se desplegará un segundo servidor FastAPI.
- **Realtime:** Postgres Changes para cambios persistidos, Presence para online/offline y Broadcast para `escribiendo…`. Una pequeña integración JavaScript del frontend administrará las suscripciones; las reglas de negocio permanecerán en Python.
- **Sin Redis:** una sola instancia del backend para la demostración.
- **Offline:** últimos 50 mensajes por conversación en IndexedDB; al abrir hacia atrás se consultarán 30 mensajes adicionales por página mientras haya conexión. La cola offline se limita a mensajes de texto.

## 3. Stack acordado

| Área | Tecnología | Responsabilidad |
|---|---|---|
| Lenguaje | Python 3.13.7 | Backend y lógica de negocio |
| Entorno y dependencias | uv | Entorno virtual, dependencias y lockfile |
| Framework web | Reflex | Interfaz, páginas, componentes, estado y servidor de la aplicación |
| API REST | FastAPI integrado en Reflex | Endpoints HTTP propios |
| Validación | Pydantic | Validación de entrada y salida |
| ORM | SQLAlchemy 2 (async) | Acceso a PostgreSQL |
| Driver PostgreSQL | Psycopg 3 | Conexión a Supabase PostgreSQL |
| Migraciones | Alembic | Esquema, restricciones, índices y SQL de políticas |
| Base de datos | Supabase PostgreSQL | Persistencia de Chatly |
| Autenticación | Supabase Auth | Registro, login, confirmación, refresh y recuperación |
| Tiempo real | Supabase Realtime | Postgres Changes, Presence y Broadcast |
| Archivos | Supabase Storage | Fotografías en bucket privado |
| Correo | Brevo SMTP Free | Confirmación y recuperación de cuentas; verificar límites vigentes antes de la demo |
| Pruebas | pytest, pytest-asyncio, pytest-cov, httpx | Pruebas unitarias e integración |
| Calidad | Ruff | Lint y formato |
| Offline/PWA | Service Worker e IndexedDB | Caché y cola local de mensajes |
| Despliegue | Render Free | Aplicación web y backend |

**Nota de seguridad para RLS con conexión PostgreSQL directa:** el backend debe verificar el JWT de Supabase y establecer el contexto del usuario dentro de cada transacción (por ejemplo, mediante una variable local de transacción). El rol de conexión no debe tener `BYPASSRLS`. El equipo debe probar que el contexto no se filtra entre peticiones al reutilizar conexiones del pool. No debe asumirse que `auth.uid()` recibe automáticamente el JWT cuando se utiliza una conexión PostgreSQL directa.

## 4. Calendario general y principales hitos

| Hito | Fechas | Resultado esperado |
|---|---|---|
| M0 — Repositorio preparado | 2–8 nov 2026 | Proyecto reproducible, Reflex arranca, dependencias, Git y CI básicos |
| M1 — Fundamentos técnicos | 9–22 nov 2026 | Arquitectura, configuración, conexión DB, Alembic y prueba de contexto RLS |
| M2 — Identidad y perfiles | 23 nov–6 dic 2026 | Auth, confirmación de correo, perfil, alias y búsqueda |
| M3 — Conversaciones y grupos | 7–20 dic 2026 | Chats privados, grupos, membresías históricas y reglas de administración |
| M4 — Mensajería funcional | 21 dic 2026–17 ene 2027 | Mensajes, edición, eliminación, respuestas, reacciones y lecturas |
| M5 — Tiempo real | 18–31 ene 2027 | Postgres Changes, Presence, Broadcast y reconexión |
| M6 — Encuestas | 1–14 feb 2027 | Encuestas, votos, cambios de voto y resultados en vivo |
| M7 — Integridad, auditoría y seguridad | 15–28 feb 2027 | Borrado lógico, versiones, auditoría, RLS y casos de membresía probados |
| M8 — Storage y datos demo | 1–14 mar 2027 | Fotografías privadas, SMTP operativo y cinco cuentas/datos de prueba |
| M9 — PWA y offline | 15–28 mar 2027 | Instalación PWA, caché de 50 mensajes y cola offline idempotente |
| M10 — Integración y congelación funcional | 29 mar–11 abr 2027 | Flujos completos, pruebas end-to-end y congelación de funcionalidades |
| M11 — Despliegue y aceptación | 12–25 abr 2027 | Render, configuración de producción demo, documentación y ensayo |
| M12 — Entrega | 26–30 abr 2027 | Código congelado, versión etiquetada y demostración final |

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

- [ ] Definir arquitectura por capas: páginas/componentes, estados Reflex, API, servicios, repositorios, modelos e integraciones.
- [ ] Crear configuración central con Pydantic Settings.
- [ ] Implementar engine SQLAlchemy asíncrono, pool, sesiones y manejo de transacciones.
- [ ] Configurar Psycopg 3 y conexión Supabase Session Pooler.
- [ ] Configurar `target_metadata` de Alembic y convenciones de nombres para constraints e índices.
- [ ] Crear modelos base y convenciones comunes: UUID, timestamps, estado lógico y campos de auditoría técnica.
- [ ] Diseñar y probar el mecanismo de identidad RLS para conexiones PostgreSQL directas.
- [ ] Verificar el aislamiento de identidad entre transacciones con pool de conexiones.
- [ ] Crear manejo centralizado de errores de API y respuestas consistentes.
- [ ] Añadir logs de aplicación sin exponer tokens, contraseñas ni datos privados.
- [ ] Crear pruebas de conexión, transacción, rollback y contexto RLS.
- [ ] Elaborar primer diagrama de arquitectura y flujo de una petición.

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

## Iteración 2 — Autenticación, perfiles y descubrimiento

**Fechas:** 23 de noviembre–6 de diciembre de 2026  
**Objetivo:** permitir que los usuarios creen cuentas verificadas y encuentren a otros participantes.

### Tareas

- [ ] Configurar Supabase Auth: correo/contraseña, confirmación obligatoria y recuperación.
- [ ] Configurar URLs de redirección de desarrollo (`localhost`) y futura demo.
- [ ] Configurar SMTP externo en Supabase Auth y probar confirmación/recuperación con direcciones reales.
- [ ] Revisar límites de Auth y del proveedor de correo; registrar el procedimiento de reenvío de confirmación.
- [ ] Implementar verificación de JWT en backend mediante claves públicas/JWKS y validaciones de issuer, audience/claims, firma y expiración según configuración.
- [ ] Implementar guardas de rutas y estado de sesión en Reflex.
- [ ] Crear `profiles` y `user_contacts`.
- [ ] Implementar creación/sincronización de perfil al registrar usuario.
- [ ] Implementar normalización del correo y búsqueda exacta sin exponerlo en resultados.
- [ ] Implementar alias único, formato 3–20 caracteres y normalización case-insensitive.
- [ ] Implementar cambio de alias con periodo de espera de 30 días y auditoría.
- [ ] Crear pantallas en español: registro, login, confirmación pendiente, reenvío, recuperación y perfil.
- [ ] Crear pruebas de confirmación bloqueante, expiración de sesión, alias duplicado y privacidad del correo.

### Entregables

- Flujos de registro/login/confirmación/recuperación.
- Perfiles y búsqueda.
- Migraciones y políticas iniciales.
- Pruebas de autenticación y privacidad.

### Criterios de salida

- Un usuario no verificado no puede acceder a funcionalidades de chat.
- El JWT se verifica en backend y el actor se deriva del token, no de un `user_id` enviado por el cliente.
- La búsqueda por correo exige coincidencia exacta y no revela el correo.
- No pueden existir alias duplicados ignorando mayúsculas/minúsculas.

## Iteración 3 — Conversaciones, grupos y membresías

**Fechas:** 7–20 de diciembre de 2026  
**Objetivo:** construir el núcleo de conversaciones y aplicar las reglas históricas de pertenencia.

### Tareas

- [ ] Crear `conversations` con tipos `direct` y `group`.
- [ ] Crear `conversation_memberships` con periodos de entrada/salida, rol, actor que añadió/expulsó y estado.
- [ ] Crear `conversation_user_preferences` para ocultar chats de forma individual.
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

### Entregables

- Conversaciones privadas y grupales.
- Gestión completa de membresías.
- Preferencias individuales de visibilidad.
- Mensajes de sistema.
- Pruebas de reglas de grupos.

### Criterios de salida

- No se crean chats privados duplicados.
- Un grupo no supera diez integrantes activos ni se crea con menos de tres.
- Solo existe un administrador activo.
- Un antiguo integrante no accede a mensajes de periodos en los que no perteneció al grupo.
- «Salir y eliminar» no afecta la conversación de los demás.

## Iteración 4 — Mensajería esencial

**Fechas:** 21 de diciembre de 2026–3 de enero de 2027  
**Objetivo:** enviar, guardar, consultar y paginar mensajes de texto.

### Tareas

- [ ] Crear `messages` con tipos `text`, `system` y `poll` (el tipo `poll` se completará en la iteración de encuestas).
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

- [ ] Crear `message_versions` y almacenar la versión anterior antes de cada edición.
- [ ] Implementar edición de mensajes propios sin límite de tiempo mientras el usuario sea miembro activo.
- [ ] Mostrar etiqueta «editado» y conservar solo la versión vigente en la vista del chat.
- [ ] Implementar eliminación lógica para todos, mostrando «Se eliminó un mensaje».
- [ ] Asegurar que la consulta normal no exponga el contenido eliminado.
- [ ] Mantener respuestas existentes cuando se elimina el mensaje original; mostrar marcador en la referencia.
- [ ] Crear `message_reactions` con los siete emojis acordados.
- [ ] Implementar una reacción activa por usuario/mensaje; cambiar actualiza y eliminar marca borrado lógico.
- [ ] Definir `last_read_message_id` por participante y periodo de membresía.
- [ ] Implementar contador de no leídos y confirmación ✓✓ según los integrantes elegibles al momento del envío.
- [ ] Marcar leído cuando la conversación esté abierta y la pestaña visible.
- [ ] Incluir mensajes de sistema en historial, no leídos y confirmaciones.
- [ ] Ordenar la lista de conversaciones por actividad más reciente.
- [ ] Implementar notificaciones visuales internas, sin push ni sonido.
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

## Iteración 6 — Supabase Realtime y presencia

**Fechas:** 18–31 de enero de 2027  
**Objetivo:** actualizar las interfaces sin polling y con control de acceso.

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
- [ ] Al expulsar a un usuario, retirar inmediatamente la suscripción en cliente y hacer que el backend/DB impida nuevas lecturas y eventos; probar la ventana de autorización de conexiones ya establecidas.
- [ ] Crear pruebas con 3–5 sesiones/navegadores simultáneos.

### Entregables

- Mensajes y cambios persistidos visibles en tiempo real.
- Presencia y escritura.
- Suscripciones autorizadas por conversación.
- Pruebas multiusuario y reconexión.

### Criterios de salida

- Un mensaje guardado por un usuario aparece en los otros clientes autorizados sin recargar la página.
- Usuarios externos o expulsados no reciben nuevos eventos autorizados.
- La presencia refleja varias sesiones de un mismo usuario.
- El indicador de escritura desaparece al dejar de recibir eventos durante cinco segundos.

## Iteración 7 — Encuestas y votaciones

**Fechas:** 1–14 de febrero de 2027  
**Objetivo:** completar la función diferenciadora de Chatly.

### Tareas

- [ ] Crear `polls`, `poll_options` y `poll_votes`.
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

## Iteración 8 — Auditoría, RLS e integridad

**Fechas:** 15–28 de febrero de 2027  
**Objetivo:** consolidar la trazabilidad y validar permisos con casos adversos.

### Tareas

- [ ] Crear `audit_logs` con actor, acción, entidad, ID, fecha, valores anteriores/nuevos cuando corresponda.
- [ ] Registrar operaciones críticas: mensajes, versiones, eliminaciones, encuestas, votos, membresías, administración, perfiles y reacciones.
- [ ] Hacer que las operaciones normales solo puedan insertar registros de auditoría; no permitir editar/borrar desde la aplicación.
- [ ] Verificar que mensajes eliminados no aparezcan en consultas normales ni respuestas de API.
- [ ] Revisar todas las políticas RLS de tablas expuestas.
- [ ] Comprobar políticas para miembros activos, antiguos miembros, expulsados, reincorporados y usuarios ajenos.
- [ ] Comprobar que `user_contacts` no sea accesible desde el navegador.
- [ ] Revisar que el rol SQLAlchemy no pueda saltarse RLS.
- [ ] Probar el contexto local por transacción y ausencia de fugas en el pool.
- [ ] Probar permisos de Storage y Realtime.
- [ ] Añadir índices a claves foráneas, búsquedas, filtros de membresía y orden de mensajes.
- [ ] Revisar restricciones únicas y checks para conversaciones, miembros, alias, votos y reacciones.
- [ ] Ejecutar revisión de seguridad y rendimiento de Supabase; corregir alertas relevantes.
- [ ] Crear pruebas negativas: intentar acceder a conversaciones ajenas, cambiar autor, votar duplicado, editar mensaje ajeno, consultar correo privado, etc.

### Entregables

- Auditoría operativa.
- Matriz de permisos documentada.
- Políticas RLS revisadas.
- Pruebas de autorización e integridad.
- Esquema y migraciones revisados.

### Criterios de salida

- Cada operación crítica deja el registro de auditoría esperado.
- No hay rutas conocidas que permitan saltarse las reglas de membresía.
- Los usuarios no pueden alterar el autor de un recurso ni acceder a datos ajenos.
- Las operaciones con SQLAlchemy respetan el contexto de usuario dentro de la transacción.

## Iteración 9 — Fotografías, correo y datos de demostración

**Fechas:** 1–14 de marzo de 2027  
**Objetivo:** completar los servicios externos necesarios y preparar una demo con contenido realista.

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
- [ ] Documentar cómo se restablece/recrea el conjunto de datos demo sin duplicados.
- [ ] No guardar contraseñas reales ni secretos de cuentas demo en el repositorio.

### Entregables

- Storage privado integrado.
- Correos de Auth comprobados.
- Cinco cuentas y datos de demostración reproducibles.

### Criterios de salida

- Las fotografías no son accesibles públicamente sin autorización/enlace firmado.
- Un usuario no puede reemplazar el avatar de otra persona.
- El registro con correo real y la recuperación funcionan.
- La base demo se puede preparar de forma repetible.

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

- [ ] Integrar autenticación, perfiles, búsqueda, chats, grupos, mensajes, encuestas, Realtime, Storage y offline.
- [ ] Ejecutar pruebas end-to-end con al menos cinco usuarios/sesiones.
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
- Informe de pruebas end-to-end.
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
- [ ] Aplicar políticas RLS, publicación Realtime y políticas de Storage.
- [ ] Ejecutar seed de cinco cuentas y contenido de demostración.
- [ ] Probar registro real, confirmación y recuperación desde la URL pública.
- [ ] Probar mensajes y encuestas entre usuarios en navegadores/dispositivos distintos.
- [ ] Probar PWA desde la URL desplegada.
- [ ] Probar restauración cuando Render haya estado inactivo y documentar el tiempo de arranque.
- [ ] Revisar la política de pausa por inactividad del plan gratuito de Supabase y el estado del proyecto antes de la presentación.
- [ ] Verificar límites gratuitos vigentes de Render, Supabase y Brevo; no asumir que las cuotas permanecen iguales.
- [ ] Crear guía de usuario y guía de instalación/desarrollo.
- [ ] Completar diagramas de arquitectura, modelo de datos y flujos principales.
- [ ] Preparar guion de demostración y datos de respaldo.
- [ ] Realizar al menos dos ensayos completos con el equipo.

### Entregables

- URL pública candidata.
- Entorno Supabase configurado.
- Documentación técnica y de usuario.
- Guion de demostración.
- Lista final de defectos no bloqueantes.

### Criterios de salida

- El despliegue puede reconstruirse desde el repositorio.
- Las variables secretas no están versionadas.
- La aplicación funciona con cinco usuarios de prueba.
- Los registros con correo real y los flujos principales funcionan desde la URL pública.
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

**Chatly V1 desplegado y demostrable antes del 30 de abril de 2027**, acompañado de repositorio, documentación, modelo de datos, pruebas y guion de presentación.

---

# 6. Distribución sugerida del trabajo entre cuatro integrantes

Los nombres se dejan como Integrante A–D porque aún no se han indicado. La asignación es de **responsabilidad principal**, no una separación rígida: las funcionalidades se integran mediante PR y revisión cruzada.

| Integrante | Responsabilidad principal | Tareas habituales |
|---|---|---|
| **A — Backend y datos** | Persistencia, esquema y seguridad de base de datos | SQLAlchemy, Psycopg, Alembic, modelos, constraints, índices, transacciones, RLS, contexto de usuario y auditoría |
| **B — Servicios y reglas de negocio** | Casos de uso y API | Auth backend, perfiles, búsqueda, conversaciones, membresías, mensajes, encuestas, validaciones y servicios |
| **C — Frontend Reflex** | Interfaz y experiencia de usuario | Páginas, componentes, layouts, estados Reflex, formularios, chat, grupos, encuestas, responsive y español |
| **D — Integraciones, offline y calidad** | Cliente Realtime, PWA y automatización de pruebas/despliegue | Supabase JS, Postgres Changes, Presence, Broadcast, IndexedDB, Service Worker, pruebas E2E, CI y Render |

## Reglas de colaboración

- Cada funcionalidad debe tener un responsable principal y al menos un revisor de otro integrante.
- Las migraciones deben revisarse por A y B antes de integrarse.
- Las políticas RLS y cambios de autorización requieren revisión de A y B.
- Las integraciones de Realtime deben revisarse junto con el contrato del evento y la política RLS correspondiente.
- D no será el único responsable de probar: cada autor debe añadir pruebas de su funcionalidad.
- C y B deben acordar contratos de API/servicios antes de construir pantallas dependientes.
- Integrar cambios pequeños y frecuentemente; evitar ramas largas con muchos conflictos.

## Reparto por etapa

| Etapa | A | B | C | D |
|---|---|---|---|---|
| Setup y arquitectura | DB/CI y configuración | servicios base/API | shell Reflex y diseño UI | automatización y entorno de prueba |
| Auth y perfiles | tablas/RLS | Auth, perfiles y búsqueda | pantallas Auth/perfil | pruebas Auth y configuración SMTP |
| Conversaciones/grupos | relaciones y restricciones | reglas de grupos/membresía | lista, chat y gestión de grupo | pruebas de casos límite |
| Mensajería | mensajes/versiones/lecturas | servicios de mensajes y reacciones | interfaz de chat | contratos y pruebas de integración |
| Realtime | publicación/RLS | eventos de dominio | actualización de estados UI | cliente JS, Presence, Broadcast y reconexión |
| Encuestas | tablas y constraints | reglas de voto/cierre | cards y resultados | pruebas concurrentes y Realtime |
| Auditoría/seguridad | RLS, índices y auditoría | autorización de servicios | estados de error/permisos | pruebas negativas y revisión integral |
| Storage/offline | metadatos y acceso | servicios de archivos | UI y estados offline | Storage JS, SW, IndexedDB y sincronización |
| Entrega | migraciones/DB | API y reglas finales | pulido visual | despliegue, CI, E2E y guion demo |

---

# 7. Gestión del trabajo

## Cadencia recomendada

- **Inicio de iteración:** revisar objetivo, dividir tareas y asignar responsables.
- **Dos sincronizaciones breves por semana:** revisar avances y bloqueos.
- **Fin de iteración:** demo interna, revisión de criterios y retrospectiva.
- **Integración continua:** PR hacia `develop`, CI obligatorio y revisión cruzada.
- **Cada cambio de BD:** migración Alembic y pruebas asociadas.

## Convención de ramas

```text
main
└── develop
    ├── feature/auth-email-verification
    ├── feature/profile-and-alias-search
    ├── feature/group-memberships
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
fix: prevent duplicate poll votes
chore: configure ruff and pytest
refactor: isolate message service
test: cover group membership history
 docs: document local setup
```



## Definition of Done (DoD)

Una tarea no se considera terminada hasta que:

- Cumple sus criterios de aceptación.
- Incluye pruebas apropiadas (unitarias, integración o end-to-end según corresponda).
- Pasa `ruff check`, formato y pytest.
- Respeta autorización, RLS y reglas de membresía aplicables.
- Maneja errores y estados de carga/vacío.
- No introduce secretos ni datos privados en logs.
- Actualiza documentación cuando cambia un contrato, configuración o flujo.
- Ha sido revisada e integrada en `develop`.

---

# 8. Criterios globales de aceptación de la V1

## Identidad

- [ ] Un usuario puede registrarse, confirmar correo, iniciar sesión y recuperar contraseña.
- [ ] Un usuario no verificado no puede usar chats.
- [ ] Alias único, formato válido y cambio limitado a una vez cada 30 días.
- [ ] Búsqueda parcial por alias y exacta por correo sin revelar el correo.

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
- [ ] Caché de últimos 50 mensajes por conversación.
- [ ] Cola de texto offline con idempotencia y reintentos.
- [ ] Al cerrar sesión se advierte sobre pendientes y se limpia la caché.

## Auditoría y seguridad

- [ ] Operaciones críticas registradas con actor, acción, entidad, fecha y valores anteriores/nuevos cuando corresponda.
- [ ] Los borrados funcionales son lógicos.
- [ ] RLS protege las tablas y eventos según autorización.
- [ ] El backend verifica JWT y deriva la identidad del token.
- [ ] `user_contacts` no es público.
- [ ] Bucket de avatares privado y archivos accesibles solo con autorización.
- [ ] Las pruebas negativas impiden accesos cruzados y modificaciones ajenas.

## Entrega

- [ ] URL pública gratuita.
- [ ] Cinco cuentas de demostración y datos precargados.
- [ ] Registro de usuarios reales probado.
- [ ] Pruebas de los flujos principales completadas.
- [ ] README, guía de uso, arquitectura y modelo de datos publicados.
- [ ] Demostración ensayada.

---

# 9. Riesgos principales y medidas de mitigación

| Riesgo | Impacto | Mitigación / decisión de planificación |
|---|---|---|
| RLS con conexión SQLAlchemy directa | Alto: puede exponer datos si el contexto no se establece correctamente | Hacer una prueba técnica en Iteración 1; usar contexto local por transacción, rol sin `BYPASSRLS` y tests de fuga entre conexiones. |
| Autorización de Realtime tras expulsión | Alto: un antiguo miembro podría mantener una suscripción existente temporalmente | Desuscribir en cliente, validar acceso en RLS/Realtime, refrescar JWT y probar conexiones persistentes. Documentar que la revocación no es instantánea para un cliente que no coopera. |
| Offline e idempotencia | Alto: mensajes duplicados o pérdida de mensajes | Implementar UUID por mensaje, outbox, estados explícitos y pruebas de reconexión antes de ampliar el offline. |
| Complejidad de membresías históricas | Alto: historial visible incorrectamente | Modelar periodos desde Iteración 3; no reducir membresía a un booleano `is_member`. |
| Borrado lógico y auditoría | Medio/alto: el contenido eliminado podría filtrarse por una consulta secundaria | Centralizar serialización/consultas, separar historial y contenido visible, añadir pruebas negativas. |
| Correo de confirmación | Medio: límites del SMTP predeterminado o del plan gratuito | Configurar SMTP externo temprano, probar correos reales y verificar cuotas vigentes antes de la demo. |
| Servicios gratuitos | Alto para la presentación: pausa o arranque lento | Ensayar el despliegue antes de presentar y comprobar Supabase/Render con antelación. Mantener un plan de demostración local. |
| Alcance extenso para seis meses | Alto: retraso de funciones críticas | No añadir funcionalidades fuera de Q1–Q108; congelar funcionalidades el 11 de abril. Priorizar flujos verticales completos. |
| PWA en Reflex | Medio/alto: integración del Service Worker puede requerir JS específico | Hacer una prueba de instalación y caché básica antes de la fase offline; mantener offline acotado a lectura y cola de mensajes de texto. |

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
- Pruebas de autorización.
- Despliegue y cinco cuentas de demostración.

### Simplificar primero

1. Pulido visual no esencial y animaciones.
2. Cobertura offline a exactamente los últimos 50 mensajes y solo cola de texto (sin extenderla a otras acciones).
3. Afinar notificaciones visuales; mantener el contador de no leídos.
4. Refinar reportes y gráficos de pruebas, manteniendo el conjunto mínimo de pruebas de seguridad e integridad.
5. Reducir el número de datos ficticios adicionales; conservar cinco cuentas y escenarios suficientes para la demo.

No añadir llamadas, adjuntos, push, sonidos, encuestas anónimas, bots ni otras funciones excluidas.

---

# 11. Documentación que debe quedar en `docs/`

- `docs/functional-decisions.md` — las 108 decisiones aprobadas (actualizar el nombre ChatFusion a Chatly en el título, conservando la trazabilidad si se necesita).
- `docs/architecture.md` — contexto, componentes, responsabilidades y diagramas.
- `docs/database-schema.md` — entidades, campos, relaciones, restricciones e índices.
- `docs/authorization-matrix.md` — permisos por usuario, rol y periodo de membresía.
- `docs/realtime-events.md` — canales, eventos, payloads, autorización y ciclo de vida.
- `docs/offline-sync.md` — IndexedDB, outbox, idempotencia, reintentos y conflictos.
- `docs/api-contracts.md` — endpoints, validación, errores y autenticación.
- `docs/testing-strategy.md` — pirámide de pruebas y casos críticos.
- `docs/deployment.md` — Render, Supabase, SMTP, variables y recuperación.
- `docs/demo-guide.md` — cinco cuentas, escenarios y guion de demostración.

---

# 12. Definición final de éxito

Chatly V1 se considerará terminada cuando, antes del **30 de abril de 2027**, el equipo pueda desplegar y demostrar en una URL pública gratuita, con cinco cuentas de prueba y registro real, una aplicación web en español que permita conversar en privado y en grupos, gestionar membresías con historial, enviar mensajes en tiempo real, reaccionar y responder, editar/eliminar con trazabilidad, crear y votar encuestas, mostrar presencia y lectura, y consultar/enviar mensajes básicos con el comportamiento offline definido.

El propósito no es competir con WhatsApp en amplitud, sino demostrar una implementación coherente y verificable de un conjunto delimitado de funcionalidades de mensajería y toma de decisiones.
