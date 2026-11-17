"""Archiving and deleting a goal, from its row in Metas or from its own page."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from nodus.models.goal import Goal
from nodus.services.container import Services
from nodus.ui.dialogs.confirm import confirm
from nodus.ui.event_bus import EventBus

DELETE_TEXT = "Se elimina la meta «{name}». Las cuentas y sus movimientos no se tocan."


def delete_goal(parent: QWidget, services: Services, event_bus: EventBus, goal: Goal) -> bool:
    """Deletes ``goal`` once the user confirms; True if it was deleted."""
    if not confirm(parent, "Eliminar meta", DELETE_TEXT.format(name=goal.name)):
        return False
    services.goals.delete(goal.id)
    event_bus.goals_changed.emit()
    return True


def toggle_goal_archived(services: Services, event_bus: EventBus, goal: Goal) -> None:
    """Archives ``goal``, or brings it back if it was archived."""
    services.goals.set_archived(goal.id, not goal.is_archived)
    event_bus.goals_changed.emit()
