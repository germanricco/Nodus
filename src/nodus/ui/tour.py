"""The steps of the guided tour, over Inicio: where each thing is, in a minute.

Each target is marked with ``mark_target`` where its widget is built; a test checks
that every one is on screen, so renaming or moving a widget cannot leave a step behind.
"""

from __future__ import annotations

from nodus.ui.widgets.coach_marks import CoachStep

PAGES = "pages"
ACCOUNTS = "accounts"
ADD_TRANSACTION = "add-transaction"
PERIOD = "period"
HIDE_AMOUNTS = "hide-amounts"
NOTIFICATIONS = "notifications"

TOUR_STEPS = [
    CoachStep(
        PAGES,
        "Las páginas",
        "Inicio, tus cuentas, las transacciones y todo lo demás. Un clic y estás ahí.",
    ),
    CoachStep(
        ACCOUNTS,
        "Tus cuentas",
        "Cada una con su saldo. Un clic abre su página, y los grupos se pliegan para hacer lugar.",
    ),
    CoachStep(
        ADD_TRANSACTION,
        "Agregar transacción",
        "Anota un gasto, un ingreso o una transferencia desde cualquier página.",
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
        "Si alguien mira tu pantalla, el ojo oculta tus saldos y tu patrimonio neto.",
    ),
    CoachStep(
        NOTIFICATIONS,
        "Avisos",
        "Pagos que vencen, presupuestos pasados, metas alcanzadas y versiones nuevas.",
    ),
]
