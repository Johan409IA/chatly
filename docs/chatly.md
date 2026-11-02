# Chatly

> **Estado:** diseño funcional aprobado y cerrado mediante el proceso Grill Me.   
> **Plataforma:** aplicación web responsive, instalable como PWA.  
> **Idioma de la V1:** español.

Este documento reúne las 112 decisiones aceptadas durante las rondas de definición de Chatly. Cada decisión conserva su número original (Q1–Q112) para facilitar la trazabilidad. Se incluyen las reglas y consideraciones acordadas, no las alternativas descartadas.

Cuando una decisión inicial fue precisada o ampliada en una ronda posterior, se documenta aquí la regla final acordada. Este documento consolida el **diseño funcional**; no sustituye el posterior diseño técnico detallado, el esquema SQL, las migraciones ni los criterios de aceptación.

---

## 1. Contexto, propósito y alcance del proyecto

### Q1 — Naturaleza del proyecto

Chatly es un **proyecto académico de demostración**, no un producto comercial ni una aplicación destinada a producción a gran escala.

**Consideraciones:** las decisiones se optimizan para demostrar ingeniería, lógica de negocio, persistencia, autenticación, autorización, comunicación en tiempo real y sincronización, dentro del plazo del curso. No se exigen escalabilidad masiva, SLA ni moderación avanzada.

### Q2 — Equipo, plazo y experiencia

El proyecto será desarrollado por **4 integrantes**, durante aproximadamente **6 meses**, con una experiencia **media** en desarrollo frontend y backend.

**Consideraciones:** se estima una dedicación de 7–10 horas semanales por integrante. La planificación debe contemplar integración entre módulos y tiempo para pruebas; no se asumirá dedicación a tiempo completo.

### Q3 — Plataforma objetivo

La V1 será una **aplicación web responsive**, utilizable desde escritorio y móviles, e instalable como **PWA**.

**Consideraciones:** no se desarrollará una aplicación móvil nativa para Android/iOS en esta versión. Se mantendrá una sola aplicación web, con capacidades offline progresivas.

### Q4 — Libertad tecnológica y presupuesto

El equipo tiene libertad para elegir el stack y trabajará con un presupuesto de **0 USD**, utilizando planes y recursos gratuitos.

**Consideraciones:** cualquier servicio externo elegido debe tener una cuota gratuita suficiente para la demostración. Las limitaciones de los proveedores gratuitos deben documentarse y aceptarse.

### Q5 — Criterio de éxito de la V1

La V1 estará lista cuando exista una **demo desplegada en una URL pública gratuita**, con cinco cuentas de prueba precargadas y posibilidad de que personas reales se registren con sus propios correos y puedan interactuar.

**Consideraciones:** no se exige carga elevada, SLA, moderación ni soporte para miles de usuarios. Las cinco cuentas de demostración deben permitir mostrar la aplicación sin que aparezca vacía.

### Q6 — Idioma

La interfaz, los correos y los mensajes de error de la V1 estarán únicamente en **español**.

**Consideraciones:** la internacionalización y el soporte de otros idiomas quedan fuera de la primera versión.

---

## 2. Identidad, perfiles y descubrimiento de usuarios

### Q7 — Identificación y búsqueda de usuarios

Los usuarios podrán encontrarse mediante **búsqueda parcial por `@alias`** y **búsqueda exacta por correo electrónico**.

**Consideraciones:** la búsqueda por alias mostrará coincidencias a medida que se escribe. El correo se utilizará como alternativa para localizar a una persona, pero no se revelará en los resultados públicos de búsqueda.

### Q15 — Confirmación obligatoria del correo

La confirmación del correo electrónico será **bloqueante**: un usuario nuevo no podrá participar en conversaciones hasta verificar su dirección.

**Consideraciones:** la experiencia debe mostrar una pantalla del tipo «Revisa tu bandeja de entrada» e incluir la posibilidad de reenviar el enlace de confirmación. Los usuarios que participen en Chatly deben estar verificados.

### Q18 — Fotografías de perfil

Al registrarse, cada usuario tendrá un avatar predeterminado y podrá subir, cambiar o eliminar su fotografía posteriormente.

**Consideraciones:** se aceptan JPEG, PNG o WebP, con un tamaño máximo de 2 MB. Se conserva el archivo anterior en Storage cuando se cambia la foto, pero el perfil solo apunta a la fotografía vigente. Las fotografías se almacenan en un bucket privado y se accede a ellas mediante permisos adecuados y enlaces firmados de duración limitada.

### Q19 — Comportamiento de búsqueda

La búsqueda se realizará parcialmente por alias y por coincidencia exacta del correo electrónico.

**Consideraciones:** los resultados muestran nombre, `@alias` y fotografía. No muestran la dirección de correo. No se construirá un directorio público ni una agenda de contactos en V1.

### Q25 — Cuentas para la demostración

Se crearán **cinco cuentas de demostración** con datos y conversaciones precargadas. Además, se permitirá el registro independiente de usuarios reales.

**Consideraciones:** las credenciales de las cuentas de demostración se facilitarán de manera controlada; no se publicarán abiertamente dentro de la aplicación.

### Q50 — Cambio de alias

Los usuarios podrán cambiar su alias siempre que el nuevo esté disponible.

**Consideraciones:** los alias son únicos sin distinguir mayúsculas y minúsculas. El alias anterior queda disponible inmediatamente después del cambio y el cambio se registra en auditoría.

### Q56 — Información visible en los resultados de búsqueda

Al encontrar a una persona se mostrará su **nombre, `@alias` y fotografía**.

**Consideraciones:** el correo electrónico no se revela en los resultados aunque se haya utilizado para localizar al usuario.

### Q57 — Formato del alias

El alias debe cumplir estas reglas:

- Entre 3 y 20 caracteres.
- Comienza con una letra.
- Admite letras, números y guion bajo.
- Se almacena/compara en formato normalizado, sin distinguir mayúsculas y minúsculas.
- Es único en toda la aplicación.

**Ejemplo:** `@johan_dev`.

### Q73 — Almacenamiento del correo para búsquedas

El correo utilizado para localizar usuarios se mantiene en una tabla privada `user_contacts`, separada de los datos públicos del perfil.

**Consideraciones:** el correo se normaliza y se sincroniza con Supabase Auth. La tabla no tendrá acceso directo desde el navegador; las búsquedas se realizan desde el backend autorizado.

### Q74 — Fotografía de grupo

En la V1 no se permitirán fotografías personalizadas para los grupos.

**Consideraciones:** se utilizará un avatar generado automáticamente a partir del nombre o las iniciales del grupo. Esto evita ampliar el trabajo de gestión de archivos.

### Q80 — Conservación de fotografías anteriores

Cuando un usuario cambie su fotografía de perfil, el archivo anterior se conservará en Supabase Storage y se actualizará la referencia al avatar vigente.

**Consideraciones:** solo la fotografía actual se muestra en el perfil. Los archivos anteriores se conservan para trazabilidad y no se ofrecen como una galería pública.

### Q103 — Disponibilidad del alias anterior

Cuando un usuario cambie su alias, el anterior queda disponible inmediatamente para otros usuarios.

**Consideraciones:** los cambios se registran en auditoría. Se aplica un límite de frecuencia de un cambio cada 30 días (véase Q107).

### Q107 — Frecuencia de cambio de alias

Cada usuario podrá cambiar su `@alias` **una vez cada 30 días**.

**Consideraciones:** se busca evitar cambios constantes de identidad y confusiones entre participantes. El alias debe estar disponible y cumplir las reglas de formato.

---

## 3. Conversaciones privadas y grupales

### Q8 — Reglas iniciales de los grupos

El creador será el único administrador inicial; podrá añadir y quitar integrantes. Cualquier integrante podrá salir del grupo. El máximo será de **10 participantes**, incluyendo al creador.

**Consideraciones:** no habrá roles múltiples ni invitaciones mediante enlaces en la V1. Las reglas de salida, sucesión y conservación del historial se precisan en decisiones posteriores.

### Q20 — Conversación privada única

Existirá una única conversación privada por pareja de usuarios.

**Consideraciones:** si A inicia un chat con B y B posteriormente inicia uno con A, se abrirá la conversación ya existente, no se creará una duplicada.

### Q21 — Salida del administrador y opciones para salir

Si el administrador abandona el grupo, la administración pasa automáticamente al integrante activo con mayor antigüedad.

Se ofrecen dos acciones:

1. **Salir del grupo:** el usuario deja de ser miembro y conserva en su lista el historial anterior a su salida, en modo de solo lectura.
2. **Salir y eliminar:** el usuario deja de ser miembro y el grupo desaparece de su lista personal. El grupo, sus mensajes y los demás participantes no se eliminan ni se ven afectados.

**Consideraciones:** el límite de diez participantes incluye al creador. Los mensajes anteriores permanecen disponibles para quienes continúan en el grupo. La segunda opción es una operación individual de ocultación/visibilidad, no una eliminación global.

### Q30 — Alcance de «Salir y eliminar»

«Salir y eliminar» solo oculta el grupo para el usuario que ejecuta la acción.

**Consideraciones:** no elimina el grupo para los demás, no borra sus mensajes y no impide que el resto continúe utilizándolo. Se conserva el registro de la salida y de la preferencia de ocultación.

### Q35 — Expulsión de un integrante

Cuando un administrador expulsa a un integrante, este deja de tener acceso al grupo desde ese momento, pero conserva el historial de mensajes correspondiente a sus periodos anteriores de membresía en modo de solo lectura.

**Consideraciones:** no puede consultar mensajes posteriores a su expulsión, enviar mensajes, reaccionar ni votar mientras no sea miembro.

### Q36 — Reincorporación de un integrante

Si un usuario que salió o fue expulsado vuelve a ser añadido, recupera el acceso a los mensajes de sus periodos anteriores de membresía y al nuevo periodo.

**Consideraciones:** no puede consultar mensajes enviados durante el intervalo en que no perteneció al grupo. Cada reincorporación genera un periodo de membresía nuevo.

### Q45 — Salida del último integrante

Cuando el último integrante abandona el grupo, este se archiva automáticamente.

**Consideraciones:** se conserva toda la información y no se permite enviar mensajes ni iniciar nuevas interacciones. La visibilidad del historial para el último integrante depende de si eligió «Salir del grupo» o «Salir y eliminar».

### Q46 — Modificación de la información del grupo

Solo el administrador actual podrá modificar el nombre del grupo.

**Consideraciones:** no habrá imagen de grupo personalizada en V1; se usará un avatar generado automáticamente. No habrá permisos configurables para que otros integrantes modifiquen la información.

### Q47 — Transferencia de administración

No habrá transferencia manual de administración en V1.

**Consideraciones:** cuando el administrador abandona o deja de pertenecer al grupo, la administración pasa automáticamente al integrante activo con mayor antigüedad.

### Q58 — Historial de membresías

Cada entrada y salida de un grupo se registra como un periodo de membresía independiente.

**Consideraciones:** se conserva la fecha de entrada y salida de cada periodo. Solo puede existir una membresía activa por usuario y conversación. La información permite aplicar las reglas históricas de visibilidad y lectura.

### Q59 — Ocultar una conversación privada

Cada usuario podrá ocultar una conversación privada de su propia lista sin afectar a la otra persona.

**Consideraciones:** la conversación y todos sus mensajes permanecen almacenados. Cuando llegue un mensaje nuevo, la conversación vuelve a aparecer para el usuario que la había ocultado, mostrando el historial anterior. Si el propio usuario inicia una nueva actividad en ese chat, también vuelve a aparecer (véase Q76 y Q105). La preferencia es individual y se almacena en `conversation_user_preferences`.

### Q68 — Preferencias individuales de conversación

La preferencia de ocultar una conversación se guarda en una entidad independiente `conversation_user_preferences`.

**Consideraciones:** ocultar un chat es una preferencia individual y no modifica la conversación ni la membresía de otros usuarios.

### Q81 — Incorporación de integrantes

El administrador añade directamente a los usuarios que busca dentro de Chatly.

**Consideraciones:** no se necesitan solicitudes de aceptación ni invitaciones mediante enlaces en V1. El acceso comienza desde la incorporación y el usuario podrá consultar los mensajes de su periodo de membresía.

### Q86 — Evitar integrantes duplicados

Si el administrador intenta añadir a una persona que ya pertenece al grupo, el sistema detecta la membresía activa y muestra un aviso, sin crear otra.

**Consideraciones:** la base de datos debe impedir dos membresías activas simultáneas de la misma persona en una conversación. Los periodos históricos anteriores sí se conservan.

### Q87 — Nombre de grupo

El nombre del grupo tendrá entre 3 y 40 caracteres. Se permiten letras, números, espacios y caracteres comunes.

**Consideraciones:** se eliminan espacios sobrantes al principio y al final. Los nombres de grupo no necesitan ser únicos y solo el administrador puede modificarlos.

### Q89 — Mínimo de integrantes

Un grupo debe crearse con al menos **tres integrantes**, incluyendo al creador.

**Consideraciones:** el grupo puede continuar funcionando si posteriormente quedan dos integrantes. Se archiva cuando ya no quedan integrantes activos.

### Q90 — Historial del grupo al salir el último integrante

Si el último integrante elige «Salir del grupo», el grupo archivado permanece en su lista personal en modo de solo lectura. Si elige «Salir y eliminar», permanece oculto para él.

**Consideraciones:** se respeta la elección individual de salida y se conserva el historial.

### Q91 — Reactivación de grupos archivados

Un grupo archivado no podrá reactivarse.

**Consideraciones:** si los usuarios desean volver a conversar, deberán crear un grupo nuevo. Esto evita reabrir membresías y estados anteriores.

### Q97 — Mínimo de integrantes después de crear el grupo

El mínimo de tres integrantes solo se aplica al momento de crear el grupo.

**Consideraciones:** si posteriormente queda con dos integrantes, continúa activo. Solo se archiva cuando sale el último integrante.

### Q98 — Reincorporación después de «Salir y eliminar»

Si un usuario que eligió «Salir y eliminar» vuelve a ser añadido a un grupo que sigue activo, el grupo vuelve a aparecer en su lista personal.

**Consideraciones:** comienza un nuevo periodo de membresía y recupera el historial de sus periodos anteriores, pero no el contenido de los intervalos en que estuvo fuera. La preferencia de ocultación deja de impedir que el grupo aparezca tras la reincorporación.

### Q99 — Archivo manual de grupos

No se permitirá archivar manualmente un grupo que todavía tenga integrantes.

**Consideraciones:** el archivo ocurre únicamente cuando todos los integrantes han salido. No habrá una acción administrativa global adicional.

### Q104 — Permisos del antiguo integrante

Un usuario que haya abandonado o haya sido expulsado solo podrá consultar el historial de sus periodos de membresía.

**Consideraciones:** no podrá editar ni eliminar mensajes, reaccionar ni votar después de salir. La regla de solo lectura prevalece sobre los permisos normales de un participante activo.

---

## 4. Mensajes, reacciones y confirmaciones de lectura

### Q11 — Edición y eliminación de mensajes

Los usuarios pueden editar sus propios mensajes sin límite de tiempo mientras sean participantes activos. Los mensajes editados muestran la etiqueta **«editado»**.

Al eliminar un mensaje para todos, se muestra el marcador **«Se eliminó un mensaje»**. Nadie puede editar ni eliminar mensajes de otra persona.

**Consideraciones:** la eliminación es lógica; el contenido original se conserva en los registros internos y no aparece en las consultas normales del chat.

### Q12 — Reacciones

Cada usuario puede tener como máximo una reacción por mensaje. Si cambia de emoji, la reacción anterior se reemplaza.

El selector de V1 contiene estos siete emojis: 👍 ❤️ 😂 😮 😢 🙏 ✅.

**Consideraciones:** no habrá emojis arbitrarios ni un catálogo ampliado en V1.

### Q14 — Confirmaciones de lectura

Se utilizarán las marcas ✓ y ✓✓. En grupos, ✓✓ se muestra cuando todos los demás participantes que correspondían han leído el mensaje.

**Consideraciones:** el comportamiento se precisa en Q22, Q48, Q60, Q96 y Q101.

### Q22 — Lectura en grupos

En un grupo, ✓✓ aparece cuando todos los integrantes que deben contar para ese mensaje lo han leído.

**Consideraciones:** no se cuenta al emisor. Se consideran los integrantes que pertenecían al grupo cuando se envió el mensaje. Los nuevos integrantes no cuentan para mensajes anteriores; quienes abandonan o son expulsados dejan de bloquear la confirmación.

### Q33 — Conservación de versiones editadas

Se conservan todas las versiones anteriores de cada mensaje editado en la base de datos, pero en el chat solo se muestra la última versión.

**Consideraciones:** la versión vigente muestra la etiqueta «editado». No se ofrece una interfaz para consultar el historial de ediciones en V1.

### Q48 — Confirmaciones ante cambios de membresía

Para calcular ✓✓, se consideran los integrantes que pertenecían al grupo cuando se envió el mensaje.

**Consideraciones:** si un integrante sale o es expulsado sin leerlo, deja de bloquear la confirmación. Quienes se incorporan posteriormente no cuentan para mensajes anteriores a su entrada.

### Q51 — Longitud del mensaje

Los mensajes de texto tendrán un máximo de **4.000 caracteres** y admitirán saltos de línea.

**Consideraciones:** los enlaces se mostrarán como texto; no se generarán vistas previas de enlaces en V1.

### Q60 — Momento en que un mensaje se considera leído

Un mensaje se considera leído cuando la conversación está abierta y la pestaña de Chatly está visible/activa.

**Consideraciones:** tener una conversación abierta en una pestaña en segundo plano no basta para marcar mensajes como leídos.

### Q66 — Versiones de mensajes

La tabla `messages` conservará el contenido vigente y `message_versions` almacenará las versiones anteriores.

**Consideraciones:** cada versión anterior se registra con su contenido, autor de la edición y fecha. Las versiones no se guardan como un único JSON dentro del mensaje.

### Q67 — Persistencia de lecturas

Se guardará el último mensaje leído por cada participante y periodo de membresía, mediante una referencia como `last_read_message_id`.

**Consideraciones:** evita generar un registro por cada mensaje leído. La pertenencia histórica permite calcular qué mensajes correspondían a cada usuario.

### Q75 — Respuesta a mensaje eliminado

Si se elimina el mensaje original al que responde otro mensaje, la respuesta permanece y muestra «Se eliminó un mensaje» como referencia.

**Consideraciones:** eliminar un mensaje original no elimina lógicamente las respuestas que dependen de él.

### Q76 — Chat privado oculto que recibe actividad

Cuando una conversación privada oculta recibe un mensaje nuevo, vuelve a aparecer para el usuario y se muestra todo el historial anterior.

**Consideraciones:** la ocultación es una preferencia personal; no elimina ni fragmenta el historial.

### Q84 — Límite de tiempo para eliminar mensajes

No habrá límite de tiempo para que un usuario elimine sus propios mensajes mientras siga siendo participante activo.

**Consideraciones:** se conserva el contenido mediante borrado lógico y auditoría. Los antiguos integrantes no pueden eliminar mensajes después de salir.

### Q85 — Visibilidad del contenido eliminado

Los participantes solo verán el marcador «Se eliminó un mensaje».

**Consideraciones:** el contenido original se conserva internamente en las versiones/registros de auditoría, pero no se devuelve mediante las consultas normales del chat ni se ofrece un historial de mensajes eliminados.

### Q94 — Paginación del historial

Al abrir una conversación se cargan los últimos 50 mensajes. Al desplazarse hacia arriba se cargan 30 mensajes anteriores por página.

**Consideraciones:** se utiliza paginación por cursor y orden cronológico. Los mensajes anteriores se consultan desde el servidor cuando hay conexión; el límite offline de 50 se mantiene.

### Q95 — Orden de conversaciones

La lista principal de conversaciones se ordena por actividad más reciente.

**Consideraciones:** la conversación que recibió o envió el mensaje más reciente aparece primero. El contador de no leídos es independiente del orden.

### Q96 — Lecturas al salir y volver a un grupo

Al salir de un grupo, los mensajes posteriores a la salida no cuentan como no leídos para el antiguo integrante.

**Consideraciones:** al reincorporarse comienza un nuevo periodo de lectura y no se acumulan mensajes del intervalo en que estuvo fuera.

### Q100 — Mensajes informativos del sistema

Los grupos mostrarán eventos automáticos en el historial para creación, incorporación, expulsión, salida, cambio de administrador y modificación del nombre.

**Consideraciones:** son mensajes de sistema; no pueden editarse, eliminarse ni recibir reacciones. Sí cuentan para el historial, los no leídos y las confirmaciones de lectura.

### Q101 — Significado de las marcas de envío

- **✓:** el mensaje fue aceptado y guardado correctamente por el servidor.
- **✓✓:** el mensaje fue leído según las reglas de lectura acordadas.

**Consideraciones:** no habrá una tercera marca para indicar entrega al dispositivo del destinatario.

### Q105 — Chat privado oculto y mensaje enviado por el usuario

Si el usuario inicia una nueva actividad en una conversación privada que había ocultado —por ejemplo, envía un mensaje desde la búsqueda de usuarios—, la conversación vuelve a aparecer para él.

**Consideraciones:** la preferencia de ocultación no impide usar el chat. Al reaparecer se muestra el historial anterior.

### Q106 — Lectura de mensajes de sistema

Los eventos automáticos de grupo cuentan como elementos no leídos y participan en las confirmaciones de lectura.

**Consideraciones:** siguen las mismas reglas cronológicas de lectura del resto del historial, aunque no sean mensajes escritos por una persona.

---

## 5. Encuestas y votaciones

### Q9 — Tipo de votación y resultados

Cada participante podrá seleccionar una sola opción por encuesta. Los resultados se muestran agregados en tiempo real y se puede consultar quién votó por cada opción.

**Consideraciones:** las encuestas no son anónimas en V1. La visibilidad de votantes forma parte de la experiencia acordada.

### Q10 — Creación y cierre de encuestas

Cualquier participante de una conversación puede crear una encuesta. El creador es quien puede cerrarla; el cierre es definitivo e impide nuevos votos.

**Consideraciones:** las opciones quedan fijas una vez que se emite el primer voto. La edición permitida antes del primer voto se define en Q88 y Q92. Los casos en que el creador abandona o es expulsado se resuelven en Q24 y Q108.

### Q23 — Cambio de voto

Un usuario puede cambiar su voto mientras la encuesta esté abierta.

**Consideraciones:** solo existe un voto vigente por usuario y encuesta. El cambio reemplaza la opción anterior y se registra en auditoría.

### Q24 — Encuesta cuyo creador abandona el grupo

Si el creador abandona el grupo, la encuesta permanece disponible y el administrador actual puede cerrarla.

**Consideraciones:** el administrador no adquiere permiso para editar la pregunta ni las opciones. La encuesta conserva su contenido y resultados.

### Q49 — Votos de integrantes que salen

Los votos emitidos por un usuario permanecen registrados y siguen contando en los resultados aunque abandone o sea expulsado del grupo.

**Consideraciones:** mientras no sea miembro no puede cambiar su voto. Si vuelve a incorporarse y la encuesta sigue abierta, puede modificarlo conforme a la regla general.

### Q63 — Encuestas al archivar un grupo

Cuando el grupo se archiva al salir el último integrante, todas las encuestas abiertas se cierran automáticamente.

**Consideraciones:** se conservan sus resultados y se registra el cierre automático en auditoría.

### Q65 — Encuestas como mensajes especiales

Las encuestas se representan como mensajes de tipo especial dentro de `messages`, con tipo `poll` y datos relacionados en tablas independientes.

**Consideraciones:** pregunta, opciones y votos mantienen sus propias entidades; el mensaje permite ordenar la encuesta cronológicamente junto con los demás elementos del chat.

### Q69 — Persistencia del cambio de voto

Se mantiene un único registro vigente por combinación de encuesta y usuario. Cuando cambia el voto, se actualiza ese registro.

**Consideraciones:** una restricción única sobre `(poll_id, user_id)` evita duplicados. La auditoría conserva la opción anterior y la nueva.

### Q88 — Validaciones de encuestas

Las encuestas cumplirán estas restricciones:

- Pregunta: entre 5 y 200 caracteres.
- Entre 2 y 5 opciones.
- Texto de cada opción: entre 1 y 80 caracteres.
- No se permiten opciones duplicadas, ignorando mayúsculas y minúsculas.
- Un voto vigente por usuario.
- El voto puede cambiar mientras la encuesta esté abierta.
- El cierre es definitivo.

**Consideraciones:** se permite editar la pregunta/opciones antes del primer voto. Después del primer voto, quedan bloqueadas.

### Q92 — Quién puede modificar una encuesta antes del primer voto

Solo el creador puede modificar la pregunta y las opciones antes de que exista el primer voto.

**Consideraciones:** el administrador no puede editar encuestas ajenas. Su excepción de autoridad consiste en poder cerrar una encuesta cuyo creador ya no pertenece al grupo.

### Q93 — Eliminación de encuestas

El creador puede eliminar lógicamente una encuesta si todavía no tiene votos. Una vez emitido algún voto, solo puede cerrarla.

**Consideraciones:** la encuesta eliminada y sus datos se conservan internamente; no se eliminan físicamente. Si tiene votos, no se permite eliminarla para no perder la trazabilidad de la participación.

### Q108 — Creador expulsado antes del primer voto

Si el creador de una encuesta es expulsado antes del primer voto, la encuesta permanece disponible, pero nadie puede modificarla. El administrador actual puede cerrarla.

**Consideraciones:** se conserva la responsabilidad de edición del creador y la autoridad excepcional del administrador para cerrar encuestas cuando su creador ya no pertenece al grupo.

---

## 6. Presencia, tiempo real y notificaciones

### Q13 — Información de presencia

Se mostrará únicamente el estado **en línea** y el indicador **«escribiendo…»**.

**Consideraciones:** no se implementará «última vez visto» en V1 por las reglas adicionales de privacidad y configuración que implicaría.

### Q16 — Mecanismo de tiempo real

Se utilizará **Supabase Realtime** para distribuir eventos y gestionar la presencia de los usuarios.

**Consideraciones:** se elige Realtime en lugar de depender exclusivamente de `Reflex SharedState`. No se duplicarán mecanismos para distribuir los mismos eventos.

### Q37 — Distribución de mecanismos Realtime

La distribución funcional acordada es:

| Funcionalidad | Mecanismo |
|---|---|
| Nuevos mensajes y cambios persistidos | Postgres Changes |
| Reacciones y votos | Postgres Changes |
| Estado online/offline | Presence |
| Indicador de escritura | Broadcast |

**Consideraciones:** Postgres Changes simplifica la primera versión con cinco usuarios de prueba. Broadcast queda como opción apropiada para eventos efímeros y escenarios de mayor escala.

### Q38 — Integración de Realtime en Reflex

Se utilizará el cliente JavaScript de Supabase en el navegador, integrado con Reflex mediante una pequeña capa de JavaScript.

**Consideraciones:** la lógica de negocio, validaciones y autorizaciones permanecen en Python. JavaScript se utiliza para suscripciones y eventos del navegador; no significa desarrollar un frontend separado.

### Q77 — Duración del indicador de escritura

El indicador «escribiendo…» desaparece después de cinco segundos sin actividad de escritura.

**Consideraciones:** se actualiza mientras el usuario escribe y desaparece si deja de escribir, cambia de conversación o pierde conexión. Los eventos de escritura no se guardan en PostgreSQL.

### Q78 — Definición de usuario online

Un usuario aparece en línea mientras mantenga al menos una sesión autenticada activa de Chatly.

**Consideraciones:** si tiene varias pestañas abiertas, seguirá online mientras al menos una sesión válida permanezca conectada. Presence se utiliza para distribuir el estado a los participantes autorizados.

### Q83 — Notificaciones de la V1

Se incluirá el contador de mensajes no leídos y notificaciones visuales dentro de la aplicación cuando llegue un mensaje nuevo.

**Consideraciones:** no se implementarán notificaciones push ni sonidos en V1.

---

## 7. Funcionamiento offline y sincronización

### Q17 — Profundidad del modo offline

Se implementará un modo offline con cola de mensajes de texto pendientes.

**Consideraciones:** se podrán consultar conversaciones/mensajes previamente almacenados y redactar/enviar mensajes offline. Los mensajes se enviarán al recuperar conexión. Votar, reaccionar, editar/eliminar mensajes y otras operaciones que requieren validación del servidor no se ejecutan offline.

### Q39 — Datos almacenados localmente

Se almacenarán la lista de conversaciones y los **últimos 50 mensajes de cada conversación**.

**Consideraciones:** el usuario podrá consultar esos mensajes offline, pero no cargar mensajes más antiguos sin conexión. La caché local se elimina al cerrar sesión para proteger la privacidad en dispositivos compartidos.

### Q40 — Sincronización de mensajes pendientes

Al recuperar conexión, los mensajes pendientes se reintentan automáticamente y se marcan como enviados cuando el servidor los confirma.

**Consideraciones:** estados: `pendiente`, `enviando`, `enviado` y `fallido`. Se utiliza un identificador único generado en el dispositivo para evitar duplicados en reintentos. Si el servidor rechaza el mensaje —por ejemplo, porque el usuario dejó de pertenecer a la conversación—, se marca como fallido y se conserva localmente para que no pierda su contenido. El reintento se realiza cuando se detecta la reconexión o se vuelve a abrir la aplicación; no se presupone ejecución continua del Service Worker.

### Q62 — Cierre de sesión con mensajes pendientes

Si el usuario intenta cerrar sesión con mensajes pendientes, se muestra una advertencia y puede esperar a recuperar conexión para sincronizarlos o descartarlos explícitamente.

**Consideraciones:** después de resolver los pendientes se cierra la sesión y se limpia la caché local. No se conservará una cola de mensajes asociada a la cuenta después del cierre de sesión.

### Q79 — Encuestas offline

Las encuestas almacenadas en caché se pueden consultar en modo de solo lectura, mostrando los últimos resultados sincronizados.

**Consideraciones:** no se permite votar offline. Los resultados no se presentan como actuales si no se han sincronizado.

---

## 8. Borrado lógico, auditoría y conservación

### Q31 — Alcance del borrado lógico

El borrado lógico se aplica a los elementos eliminables de Chatly, incluyendo mensajes, reacciones, encuestas, grupos, membresías y perfiles/datos asociados cuando corresponda.

**Consideraciones:** se conserva el historial de modificaciones y operaciones. La eliminación lógica no significa borrar físicamente la fila o el objeto en el almacenamiento.

### Q32 — Consulta de auditoría

Los registros de auditoría se almacenan en la base de datos, pero no habrá una interfaz para consultarlos en la V1.

**Consideraciones:** podrán inspeccionarse durante las pruebas y la demostración mediante herramientas administrativas controladas.

### Q42 — Eliminación de cuenta

No se permitirá eliminar cuentas de usuario en la V1. Los usuarios podrán cerrar sesión.

**Consideraciones:** se evita tener que definir la eliminación o anonimización de mensajes, encuestas, votos y referencias históricas. No se realizará eliminación física automática de cuentas.

### Q43 — Operaciones auditadas

Se registrarán las operaciones importantes de negocio:

- Creación, edición y eliminación de mensajes.
- Creación y cierre de encuestas.
- Emisión y cambio de votos.
- Creación de grupos e incorporación/expulsión/salida de integrantes.
- Cambios de administración.
- Cambios de perfil y alias.
- Eliminación de reacciones.
- Otras operaciones persistentes importantes que alteren el estado del producto.

**Consideraciones:** no se registrará cada evento efímero de escritura ni cada cambio online/offline. Se busca evitar registros de poco valor y alto volumen.

### Q52 — Contenido del registro de auditoría

Cada evento de auditoría tendrá, como mínimo, actor, acción, tipo e identificador del elemento afectado, fecha y valores anteriores/posteriores cuando corresponda.

**Consideraciones:** los valores anteriores y nuevos pueden almacenarse como JSONB. Las versiones completas de mensajes se conservan en `message_versions`, para no duplicarlas innecesariamente en `audit_logs`.

### Q71 — Estructura de `audit_logs`

Se utilizará una estructura común con campos equivalentes a `actor_id`, `action`, `entity_type`, `entity_id`, `old_values`, `new_values` y `created_at`.

**Consideraciones:** `old_values` y `new_values` serán JSONB cuando corresponda. Los registros serán de solo inserción desde las operaciones normales de la aplicación; no se ofrecerá edición o borrado de auditoría desde la interfaz. Se conservarán durante toda la vida de la demostración.

---

## 9. Arquitectura, autenticación, autorización y persistencia

### Q27 — Despliegue gratuito

Se utilizará **Render Free** para desplegar Reflex/backend, **Supabase Free** para los servicios gestionados y **Brevo Free** para correos de autenticación. Se utilizará la URL pública gratuita de Render.

**Consideraciones:** se aceptan las limitaciones de los planes gratuitos: Render puede suspender servicios inactivos y tardar en reactivarlos; su sistema de archivos es temporal, por lo que los datos y fotografías deben permanecer en Supabase. Supabase Free puede pausar proyectos inactivos y tiene cuotas de base de datos y almacenamiento. La aplicación debe probarse antes de la demostración.

### Q28 — Dedicación semanal

La planificación asumirá entre **7 y 10 horas semanales por integrante** (aproximadamente 28–40 horas semanales de trabajo conjunto).

**Consideraciones:** las tareas se repartirán entre cuatro personas y se reservará tiempo para integración y pruebas.

### Q34 — Fecha de entrega

La fecha límite de entrega es el **30 de abril de 2027**.

**Consideraciones:** las últimas tres o cuatro semanas deben reservarse preferentemente para integración, pruebas, correcciones, documentación y preparación de la demostración. No se deben incorporar funcionalidades nuevas durante ese periodo.

### Q41 — Entidades iniciales del modelo de datos

La estructura conceptual inicial incluye:

1. `profiles`
2. `conversations`
3. `conversation_memberships`
4. `messages`
5. `message_versions`
6. `message_reactions`
7. `polls`
8. `poll_options`
9. `poll_votes`
10. `audit_logs`

Posteriormente se añadieron `user_contacts` y `conversation_user_preferences` (Q73 y Q68).

**Consideraciones:** las tablas deberán reflejar membresías históricas, tipos de mensajes, encuestas relacionadas con mensajes, votos vigentes y preferencias individuales. La lista es conceptual; campos, tipos, índices y restricciones se concretarán en el diseño técnico.

### Q44 — Separación de responsabilidades con Supabase

Se utilizará una arquitectura híbrida:

- La lógica de negocio y las operaciones principales pasan por el backend Python.
- Supabase Auth gestiona identidad, registro, login y sesiones.
- El navegador puede usar el cliente de Supabase para suscripciones Realtime y las operaciones de Storage que se autoricen expresamente.
- Las operaciones de negocio y sus reglas permanecen bajo control de Python.

**Consideraciones:** las credenciales privilegiadas nunca se exponen en el navegador. Storage utiliza bucket privado y políticas de acceso. Las suscripciones directas requieren autorización por usuario y conversación.

### Q53 — Verificación de identidad

El backend verifica el JWT de Supabase Auth y obtiene de él la identidad del usuario.

**Consideraciones:** el backend nunca confía en un `user_id` enviado libremente por el navegador. La identidad del actor se obtiene del token validado y se utiliza para autorizar cada operación.

### Q54 — Row Level Security

Se aplicarán políticas RLS a las tablas expuestas en Supabase y se limitarán las consultas/eventos a los datos autorizados para cada usuario.

**Consideraciones:** las políticas deben contemplar membresías activas e históricas, periodos de participación, acceso a mensajes, perfiles y Realtime. La autorización de estar autenticado no basta: también debe comprobarse la pertenencia o el permiso sobre el recurso.

### Q55 — Gestión de migraciones

**Alembic** será responsable de gestionar las migraciones del esquema propio de Chatly: tablas, restricciones, índices y políticas SQL/RLS.

**Consideraciones:** no se modificarán directamente las tablas internas gestionadas por Supabase Auth, Storage o Realtime. No se mantendrán dos sistemas de migraciones compitiendo por las mismas tablas.

### Q61 — Expulsión y suscripciones Realtime

Cuando un usuario sea expulsado, el cliente debe desconectar inmediatamente sus suscripciones a los canales del grupo. Los JWT tendrán una duración aproximada de **10 minutos** para reducir la ventana de exposición de una autorización anterior.

**Consideraciones:** la desuscripción del cliente y la expiración del token no garantizan revocación instantánea de una conexión que no coopere. Deben comprobarse autorizaciones y renovaciones; los eventos no deben seguir enviándose a usuarios que hayan perdido acceso. La duración de 10 minutos es una decisión para la V1, no una garantía de revocación inmediata.

### Q64 — Una tabla para conversaciones privadas y grupales

Se utilizará una única tabla `conversations` con un campo de tipo que distinga `direct` y `group`.

**Consideraciones:** ambas modalidades comparten propiedades y se relacionan con participantes mediante `conversation_memberships`. Se impondrá una restricción para evitar conversaciones privadas duplicadas entre la misma pareja de usuarios.

### Q70 — Persistencia de reacciones

Se mantendrá una fila por usuario y mensaje. Cambiar el emoji actualizará el registro; eliminar la reacción establecerá su estado/fecha de eliminación lógica.

**Consideraciones:** una restricción única sobre `(message_id, user_id)` impide reacciones vigentes duplicadas. Los cambios se conservan en auditoría.

### Q72 — RLS con SQLAlchemy y conexión directa

El backend verificará primero el JWT; después abrirá una transacción de PostgreSQL y establecerá el identificador autenticado en un contexto local de la transacción, por ejemplo `app.current_user_id`. Las políticas RLS utilizarán ese contexto para decidir qué filas puede consultar o modificar el usuario.

**Consideraciones importantes:** una conexión PostgreSQL directa no recibe automáticamente el contexto JWT que Supabase establece en las solicitudes a su API REST. Por tanto, no se debe asumir que `auth.uid()` funcionará automáticamente con la conexión directa de SQLAlchemy. El rol de conexión no debe tener `BYPASSRLS`; el contexto debe establecerse de forma local a cada transacción y no filtrarse a la siguiente petición del pool. La identidad se deriva exclusivamente del JWT validado, no de datos arbitrarios enviados por el navegador.

### Q82 — Inicio de conversaciones privadas

Cualquier usuario registrado y verificado puede iniciar una conversación privada con otro usuario encontrado mediante la búsqueda.

**Consideraciones:** no habrá solicitudes de conversación ni aprobación previa del destinatario en V1.

### Q102 — Privacidad de las fotografías

Las fotografías se almacenarán en un **bucket privado** de Supabase Storage.

**Consideraciones:** solo usuarios autenticados y autorizados podrán acceder a ellas. Se utilizarán políticas de Storage y enlaces firmados de duración limitada cuando corresponda. Una URL firmada permite acceso durante su vigencia, por lo que no debe tener una duración innecesariamente larga.

### Stack tecnológico acordado

| Área | Tecnología | Responsabilidad |
|---|---|---|
| Lenguaje | Python | Backend y lógica de negocio |
| Framework web full-stack | Reflex | Interfaz, páginas, componentes y estado de la aplicación |
| API REST | FastAPI integrado en Reflex | Endpoints HTTP propios, sin desplegar un segundo servidor independiente |
| Validación | Pydantic | Validación de datos y solicitudes |
| ORM | SQLAlchemy 2 | Acceso a PostgreSQL |
| Migraciones | Alembic | Evolución del esquema propio de Chatly |
| Base de datos | Supabase PostgreSQL | Persistencia de perfiles, conversaciones, mensajes, encuestas y auditoría |
| Autenticación | Supabase Auth | Registro, login, confirmación y recuperación de contraseña |
| Tiempo real | Supabase Realtime | Postgres Changes, Broadcast y Presence según la función |
| Archivos | Supabase Storage | Fotografías de perfil en bucket privado |
| Correos | Brevo SMTP Free | Confirmación y recuperación de cuenta |
| Dependencias | uv | Gestión de entorno y paquetes Python |
| Pruebas | pytest | Pruebas unitarias e integración de servicios/API |
| Offline | PWA, Service Worker e IndexedDB | Caché y mensajes pendientes |

**Decisiones de infraestructura:** no se utilizará Redis inicialmente; habrá una única instancia del backend. No se añadirá Django Channels ni un segundo servidor FastAPI. La integración JavaScript se limitará a las necesidades de Realtime y del navegador.

---

## 10. Reglas finales y casos límite

### Q26 — Moderación

No se implementará un sistema de moderación, bloqueo ni reportes en V1.

**Consideraciones:** aunque no exista un módulo de moderación, sí se aplican controles obligatorios de autenticación, autorización, pertenencia a conversaciones y autoría de operaciones.

### Q29 — Reserva de tiempo para la entrega

La planificación debe reservar las últimas tres o cuatro semanas antes del 30 de abril de 2027 para integración, pruebas, correcciones, documentación y preparación de la demostración.

**Consideraciones:** durante ese periodo no se deben añadir funcionalidades nuevas.

Las decisiones sobre mensajes de sistema, modo de solo lectura de antiguos integrantes, visibilidad de chats privados y encuestas cuyo creador deja el grupo se encuentran documentadas en sus respectivas secciones temáticas (Q100, Q104–Q106 y Q108).


---

## 11. Exclusiones expresas de la V1

Las siguientes funcionalidades quedan fuera del alcance inicial:

- Aplicaciones móviles nativas para Android/iOS.
- Llamadas de voz y vídeo.
- Archivos adjuntos e imágenes dentro de las conversaciones.
- Fotografías personalizadas de grupos.
- Notificaciones push.
- Sonidos de notificación.
- Encuestas anónimas.
- Bots y automatizaciones.
- Solicitudes de conversación o aprobación de contactos.
- Invitaciones a grupos mediante enlaces.
- Directorio público o importación de agenda de contactos.
- Última conexión/«última vez visto».
- Moderación avanzada, bloqueo y reportes.
- Panel de auditoría para usuarios o administradores.
- Eliminación de cuentas de usuario.
- Reactivación de grupos archivados.
- Internacionalización/multidioma.
- Reacciones con emojis arbitrarios.
- Vistas previas enriquecidas de enlaces.

---

## 12. Entregables posteriores al diseño funcional

El diseño funcional está aprobado. Antes de implementar, el equipo debe producir y revisar los siguientes entregables:

1. **Arquitectura técnica detallada:** estructura de carpetas, capas, responsabilidades, comunicación Reflex/FastAPI/Supabase y manejo de sesiones.
2. **Modelo de datos definitivo:** campos, tipos, claves primarias/foráneas, restricciones únicas, índices y relaciones para todas las tablas.
3. **Políticas de autorización:** políticas RLS para lectura, escritura, membresías históricas, Storage y canales Realtime.
4. **Migraciones:** estrategia Alembic para las tablas propias de Chatly y pruebas de migración.
5. **Criterios de aceptación:** condiciones verificables por funcionalidad y pruebas de casos normales y límite.
6. **Pruebas:** reglas de negocio, permisos, sincronización, idempotencia de mensajes offline y casos de membresía.
7. **Roadmap:** fases, tareas, entregables y responsables para los cuatro integrantes.
8. **Plan de demostración:** cinco cuentas de prueba, datos precargados, URL pública y guion de escenarios para demostrar mensajería, grupos y encuestas.

## 13. Identidad y perfil (decisiones adicionales)

### Q109 — Edad del usuario

Cada usuario tendrá **fecha de nacimiento** obligatoria y una **edad** derivada de ella.

**Consideraciones:** la edad no se almacena como columna; se calcula restando el año actual menos el año de nacimiento y descontando un año si el cumpleaños aún no ha ocurrido en el año en curso. Se configura y se puede editar desde el perfil. Solo se admiten usuarios de **18 a 120 años**; el registro se rechaza fuera de ese rango. La edad se muestra únicamente en el perfil, a usuarios autenticados y verificados, y nunca en los resultados de búsqueda ni en la lista de participantes de un grupo. La fecha de nacimiento exacta solo la ve su dueño.

### Q110 — Género del usuario

El género será obligatorio y tendrá un catálogo cerrado de dos valores: **femenino** y **masculino**.

**Consideraciones:** se solicita en el registro y se puede editar desde el perfil. No existe la opción «prefiero no decir». Se muestra solo en el perfil, a usuarios autenticados y verificados, y nunca en los resultados de búsqueda ni en la lista de participantes.

### Q111 — Nombre visible

Cada usuario tendrá un nombre visible obligatorio, distinto del `@alias`.

**Consideraciones:** admite entre **2 y 60 caracteres**, se solicita en el registro y se puede editar en cualquier momento. No es único: la diferenciación entre usuarios recae en el alias único. El nombre visible aparece en los resultados de búsqueda junto al alias y la fotografía (Q56).

### Q112 — Búsqueda por alias

La búsqueda por alias se disparará a partir de **2 caracteres** escritos.

**Consideraciones:** no distingue mayúsculas y minúsculas y excluye al propio usuario de los resultados. Mantiene la regla de Q19: nunca se revela el correo electrónico. La búsqueda exacta por correo sigue disponible como alternativa (Q7).

---

## 14. Nota sobre el alcance de este documento

Este archivo registra las decisiones aceptadas durante la entrevista Grill Me. No representa todavía una especificación SQL lista para ejecutar ni una garantía de que todos los detalles de implementación estén resueltos. Los campos, restricciones, políticas, flujos de error y criterios de aceptación deben concretarse en la siguiente etapa de diseño técnico.

**Principio rector de Chatly:** las conversaciones permiten intercambiar ideas y las encuestas ayudan a convertir esas ideas en decisiones, manteniendo la coherencia de los permisos, el historial y la trazabilidad de las operaciones.
