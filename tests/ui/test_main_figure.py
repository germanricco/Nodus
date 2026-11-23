"""A page shows at most one hero figure, the answer to its question, and the boxes under
it are all alike (plan 029a, 5.2)."""

from datetime import date

from demo_data import load_demo_data
from PySide6.QtWidgets import QLabel

from nodus.ui.navigation import DetailId, PageId
from nodus.ui.widgets.figure_tile import FigureTile
from nodus.ui.widgets.hero_figure import HeroFigure


def shown(page, kind) -> list:
    """The widgets of ``kind`` on view: a hidden tab of Análisis has its own."""
    return [w for w in page.findChildren(kind) if w.isVisibleTo(page)]


def test_every_box_has_the_same_size_of_figure_and_the_hero_a_larger_one(qtbot):
    tiles = [FigureTile(caption, QLabel("$ 1")) for caption in ("Entró", "Salió")]
    hero = HeroFigure("Saldo", QLabel("$ 1"))
    for widget in (*tiles, hero):
        qtbot.addWidget(widget)
    assert {tile.value.objectName() for tile in tiles} == {"StatValue"}
    assert hero.value.objectName() == "StatValueHero"


def test_every_page_has_at_most_one_hero_figure(window, services):
    load_demo_data(services, date.today())
    window._event_bus.emit_all()
    visits = [(page_id,) for page_id in PageId] + [
        (DetailId.ACCOUNT, services.accounts.list_accounts()[0].id),
        (DetailId.GOAL, services.goals.list_goals()[0].id),
        (DetailId.PAYEE, services.payees.list_payees()[0].id),
    ]
    with_hero = []
    for visit in visits:
        if len(visit) == 1:
            window.show_page(visit[0])
        else:
            window.show_detail(*visit)
        heroes = shown(window.current_page, HeroFigure)
        assert len(heroes) <= 1, visit
        if heroes:
            with_hero.append(visit[0])
    # The pages whose question has one answer; Análisis shows peers, all in boxes.
    assert {PageId.RECURRING, DetailId.ACCOUNT, DetailId.GOAL, DetailId.PAYEE} <= set(with_hero)
    assert PageId.ANALYSIS not in with_hero
