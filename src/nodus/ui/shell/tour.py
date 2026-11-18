"""The steps of the guided tour, over Inicio: where each thing is and what it is for.

The steps go as the window reads: the sidebar from top to bottom, then the bar above the
page from left to right (a test checks it). Each target is marked with ``mark_target``
where its widget is built; a test checks that every one is on screen, so renaming or
moving a widget cannot leave a step behind.
"""

from __future__ import annotations

from nodus.ui.shell.coach_marks import CoachStep

PAGES = "pages"
ACCOUNTS = "accounts"
SETTINGS = "settings"
ADD_TRANSACTION = "add-transaction"
PERIOD = "period"
HIDE_AMOUNTS = "hide-amounts"
HELP = "help"
FEEDBACK = "feedback"
NOTIFICATIONS = "notifications"

TOUR_STEPS = [
    CoachStep(
        PAGES,
        "Las páginas",
        "En Transacciones buscas y editas tus movimientos; en Recurrentes, lo que pagas"
        " todos los meses. Presupuestos pone un límite a cada categoría, Metas sigue lo que"
        " ahorras y Análisis muestra cómo cambian tus números mes a mes.",
    ),
    CoachStep(
        ACCOUNTS,
        "Tus cuentas",
        "Cada una con su saldo de hoy. Un clic abre su página, con su historia y sus"
        " movimientos. Los grupos se pliegan para hacer lugar.",
    ),
    CoachStep(
        SETTINGS,
        "Ajustes",
        "Las cotizaciones del dólar y del euro, las copias de tus datos, el tema claro u"
        " oscuro y el recordatorio de fin de mes.",
    ),
    CoachStep(
        ADD_TRANSACTION,
        "Agregar transacción",
        "Desde cualquier página: un gasto, un ingreso o una transferencia, también en"
        " cuotas o como reembolso de un gasto.",
    ),
    CoachStep(
        PERIOD,
        "El período",
        "Elige qué mira el Inicio: este mes, los últimos 3, 6 o 12 meses, el año o las"
        " fechas que quieras.",
    ),
    CoachStep(
        HIDE_AMOUNTS,
        "Ocultar montos",
        "Si alguien mira tu pantalla, el ojo tapa todos los montos. Otro clic los muestra.",
    ),
    CoachStep(
        HELP,
        "Ayuda",
        "Cómo se hace cada cosa y los atajos de teclado. Se abre al costado, en el tema de"
        " la página donde estás. También con F1.",
    ),
    CoachStep(
        FEEDBACK,
        "Enviar comentarios",
        "¿Algo no anda o se te ocurre una mejora? Este botón abre un formulario para contarlo.",
    ),
    CoachStep(
        NOTIFICATIONS,
        "Avisos",
        "Pagos que vencen, presupuestos pasados, metas alcanzadas y versiones nuevas."
        " Para volver a ver este recorrido, búscalo en la Ayuda o en Ajustes.",
    ),
]
