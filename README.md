# Chatly

Chatly es una aplicación web responsive de mensajería en español, diseñada para facilitar conversaciones privadas y grupales y ayudar a sus participantes a tomar decisiones mediante encuestas. Se puede instalar como PWA y ofrece capacidades offline progresivas.

## Funcionalidades

- **Perfiles y descubrimiento de personas:** registro con verificación de correo, perfil con nombre visible, alias único y fotografía; búsqueda por alias o correo sin revelar el correo en los resultados.
- **Conversaciones privadas y grupales:** un chat privado único por pareja; grupos de hasta 10 personas, con administración, gestión de integrantes e historial sujeto a los periodos de membresía.
- **Mensajería:** envío de texto, edición y eliminación de mensajes propios, respuestas, reacciones con un conjunto definido de emojis y confirmaciones de lectura.
- **Encuestas:** creación de encuestas en conversaciones, votación de una opción por persona, cambio de voto mientras estén abiertas y resultados en tiempo real.
- **Actualizaciones en tiempo real:** presencia en línea, indicador de escritura, mensajes, reacciones, votos y contador de mensajes no leídos.
- **Uso offline progresivo:** consulta de conversaciones y mensajes almacenados, redacción de mensajes sin conexión y sincronización al recuperar la conexión.
- **Trazabilidad:** registro interno de operaciones importantes y conservación del historial conforme a las reglas de cada conversación.

## Requisitos

- Python `>=3.13,<3.14`
- [uv](https://docs.astral.sh/uv/)
- Una configuración de Supabase para la base de datos y los servicios de autenticación, Realtime y Storage.

## Clonar el repositorio

```sh
git clone https://github.com/Johan409IA/chatly.git
cd chatly
```

## Instalación y configuración

Instala las dependencias del proyecto:

```sh
uv sync
```

Crea el archivo local de variables de entorno a partir de la plantilla:

```sh
# macOS / Linux
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

Configura en `.env` los valores de Supabase indicados en `.env.example`. No compartas ese archivo ni publiques sus credenciales.

## Ejecución en desarrollo

```sh
uv run reflex run
```

## Tests

```sh
uv run pytest
```

## Documentación

- [Diseño funcional de Chatly](docs/chatly.md): reglas, funcionalidades, casos límite y decisiones tecnológicas.
- [Arquitectura](docs/architecture.md)
- [Esquema de base de datos](docs/database-schema.md)
- [Contratos de API](docs/api-contracts.md)
- [Eventos en tiempo real](docs/realtime-events.md)
- [Matriz de autorización](docs/authorization-matrix.md)
- [Roadmap](docs/roadmap.md)
