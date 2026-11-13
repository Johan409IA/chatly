"""Layout dividido de las pantallas de autenticación (login y registro).

Reproduce el diseño de referencia de `assets/ux-ui/`: panel izquierdo con la
red de nodos luminosos y el logotipo «CHATLY», y panel derecho oscuro con el
contenido de la pantalla. Solo presentación: las reglas viven en
`state/auth_state.py` y los textos en las páginas.

El panel de marca se dibuja con SVG (nodos y líneas) para que sea nítido en
cualquier resolución y no dependa de imágenes externas.
"""

import reflex as rx

# Lienzo de la red (600x760, el del panel de marca) con los nodos:
# x, y, radio y color.
_NODES: tuple[tuple[int, int, int, str], ...] = (
    (120, 90, 10, "cyan"),
    (300, 60, 6, "violet"),
    (470, 130, 12, "cyan"),
    (200, 200, 8, "violet"),
    (390, 250, 10, "pink"),
    (90, 330, 7, "cyan"),
    (250, 390, 13, "cyan"),
    (440, 430, 8, "violet"),
    (140, 520, 6, "pink"),
    (540, 330, 7, "cyan"),
    (330, 560, 9, "violet"),
    (70, 230, 5, "pink"),
    (520, 220, 6, "violet"),
    (350, 160, 5, "pink"),
    (450, 640, 7, "cyan"),
    (160, 660, 8, "violet"),
)

# Aristas de la red: pares de índices de `_NODES`.
_EDGES: tuple[tuple[int, int], ...] = (
    (0, 1),
    (1, 2),
    (0, 3),
    (2, 13),
    (3, 4),
    (4, 2),
    (3, 5),
    (5, 6),
    (6, 7),
    (7, 8),
    (6, 9),
    (9, 4),
    (9, 7),
    (7, 10),
    (8, 10),
    (5, 11),
    (11, 12),
    (12, 2),
    (12, 9),
    (13, 4),
    (1, 3),
    (14, 7),
    (15, 8),
    (15, 10),
    (14, 9),
)

# Aristas brillantes: trazos largos que cruzan el panel, como en la referencia.
_STREAKS: tuple[tuple[int, int], ...] = (
    (3, 7),
    (6, 2),
    (5, 10),
)


def network_graph() -> rx.Component:
    """Red de nodos y líneas que se dibuja tras el logotipo."""
    edges = [
        rx.el.line(
            x1=_NODES[origin][0],
            y1=_NODES[origin][1],
            x2=_NODES[target][0],
            y2=_NODES[target][1],
            class_name="chatly-auth__edge",
        )
        for origin, target in _EDGES
    ]
    streaks = [
        rx.el.line(
            x1=_NODES[origin][0],
            y1=_NODES[origin][1],
            x2=_NODES[target][0],
            y2=_NODES[target][1],
            class_name="chatly-auth__edge chatly-auth__edge--streak",
        )
        for origin, target in _STREAKS
    ]
    nodes = [
        rx.el.circle(
            cx=x,
            cy=y,
            r=radius,
            class_name=(
                f"chatly-auth__node chatly-auth__node--{color} chatly-auth__node--d{index % 5 + 1}"
            ),
        )
        for index, (x, y, radius, color) in enumerate(_NODES)
    ]
    return rx.el.svg(
        *edges,
        *streaks,
        *nodes,
        view_box="0 0 600 760",
        preserve_aspect_ratio="xMidYMid slice",
        class_name="chatly-auth__net",
    )


def brand_panel() -> rx.Component:
    """Panel izquierdo: red de nodos y logotipo «CHATLY»."""
    return rx.box(
        network_graph(),
        rx.box(
            rx.text("Chatly", class_name="chatly-auth__wordmark"),
            class_name="chatly-auth__wordmark-wrap",
        ),
        class_name="chatly-auth__brand",
    )


def auth_split(*content: rx.Component) -> rx.Component:
    """Pantalla de auth en dos columnas: marca a la izquierda, contenido a la derecha."""
    return rx.box(
        brand_panel(),
        rx.box(
            rx.box(*content, class_name="chatly-auth__content"),
            class_name="chatly-auth__panel",
        ),
        class_name="chatly-auth",
    )


def auth_alert(message: rx.Var[str], info: bool = False) -> rx.Component:
    """Aviso de error o de información con el estilo oscuro de las pantallas."""
    return rx.cond(
        message != "",
        rx.box(
            rx.icon("triangle_alert" if not info else "info", size=18),
            rx.text(message, size="2"),
            class_name=(
                "chatly-auth__alert chatly-auth__alert--info" if info else "chatly-auth__alert"
            ),
        ),
        rx.fragment(),
    )


def field_block(
    label: str,
    control: rx.Component,
    hint: str = "",
    error: rx.Var[str] | None = None,
) -> rx.Component:
    """Campo con etiqueta, texto de ayuda y mensaje de error."""
    return rx.box(
        rx.text(label, class_name="chatly-auth__label"),
        control,
        rx.cond(
            hint != "",
            rx.text(hint, class_name="chatly-auth__hint"),
            rx.fragment(),
        ),
        rx.cond(
            error is not None and error != "",
            rx.text(error, class_name="chatly-auth__error"),
            rx.fragment(),
        ),
        class_name="chatly-auth__stack chatly-auth__stack--tight",
    )


def progress_dots(total: int, current: rx.Var[int]) -> rx.Component:
    """Barra de progreso del asistente: un punto iluminado por paso superado."""
    return rx.box(
        *[
            rx.box(
                class_name=rx.cond(
                    current >= index + 1,
                    "chatly-auth__progress on",
                    "chatly-auth__progress",
                ),
            )
            for index in range(total)
        ],
        class_name="chatly-auth__progress",
    )
