"""The catalog of translations: extracting the texts, compiling them and checking them.

Spanish is the source language, so the catalog holds only the other languages:
``src/nodus/locale/<code>/LC_MESSAGES/nodus.po``. The ``.po`` is versioned; the
``.mo`` that Nodus reads is compiled from it by ``build.py``, the tests and ``compile``,
and is ignored by git.

    python scripts/translations.py extract   # brings the .po up to date with the code
    python scripts/translations.py compile   # writes the .mo
    python scripts/translations.py check     # what is missing or wrong, if anything
    python scripts/translations.py review    # a page to read each screen's texts side by side
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from _common import ROOT
from babel.messages.catalog import Catalog, Message
from babel.messages.extract import extract_from_dir
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po

PACKAGE = ROOT / "src" / "nodus"
LOCALE_DIR = PACKAGE / "locale"
DOMAIN = "nodus"
LANGUAGES = ("en",)  # every language but Spanish, the source
# The functions in nodus.i18n that mark a text, with the arguments that hold it.
KEYWORDS = {"_": None, "N_": None, "ngettext": (1, 2), "pgettext": ((1, "c"), 2)}
PLACEHOLDER = re.compile(r"\{(\w*)[^{}]*\}")
ISSUES_URL = "https://github.com/germanricco/Nodus/issues"
# A fixed header, so that extracting again changes only the texts that changed.
HEADER_COMMENT = "# Nodus, translated from Spanish (the source language: see nodus/i18n.py)."
FIXED_DATE = datetime(2026, 11, 18, tzinfo=UTC)


def po_path(language: str) -> Path:
    return LOCALE_DIR / language / "LC_MESSAGES" / f"{DOMAIN}.po"


def mo_path(language: str) -> Path:
    return po_path(language).with_suffix(".mo")


def extracted() -> Catalog:
    """Every text the code marks, with the files where it appears (not the lines, so
    that editing a file does not change the whole catalog)."""
    template = Catalog(project="Nodus", msgid_bugs_address="")
    found = extract_from_dir(
        str(PACKAGE), method_map=[("**.py", "python")], keywords=KEYWORDS, comment_tags=("NOTE:",)
    )
    for filename, _lineno, message, comments, context in found:
        template.add(
            message,
            locations=[(f"nodus/{filename}", None)],
            auto_comments=comments,
            context=context,
        )
    return template


def read_catalog(language: str) -> Catalog:
    if not po_path(language).exists():
        return Catalog(locale=language, project="Nodus", msgid_bugs_address="")
    with po_path(language).open("rb") as file:
        return read_po(file, locale=language)


def write_catalog(catalog: Catalog, path: Path) -> None:
    catalog.header_comment = HEADER_COMMENT
    catalog.fuzzy = False  # a doubtful header would be left out of the .mo
    catalog.project, catalog.version = "Nodus", "1"  # the catalog, not the app
    catalog.msgid_bugs_address = ISSUES_URL
    catalog.last_translator = catalog.language_team = "Nodus"
    catalog.creation_date = catalog.revision_date = FIXED_DATE
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as file:
        write_po(file, catalog, width=100, include_lineno=False, ignore_obsolete=True)


def extract() -> None:
    """Brings each ``.po`` up to date with the code: new texts come in untranslated and
    texts the code no longer has go away. Nothing is guessed from similar texts."""
    template = extracted()
    for language in LANGUAGES:
        catalog = read_catalog(language)
        catalog.update(template, no_fuzzy_matching=True)
        write_catalog(catalog, po_path(language))
        print(f"{po_path(language).relative_to(ROOT)}: {len(catalog)} textos")


def compile_catalogs(only_if_stale: bool = False) -> None:
    """Writes each ``.mo`` from its ``.po``; with ``only_if_stale``, only those older
    than their ``.po``."""
    for language in LANGUAGES:
        po, mo = po_path(language), mo_path(language)
        if only_if_stale and mo.exists() and mo.stat().st_mtime >= po.stat().st_mtime:
            continue
        catalog = read_catalog(language)
        with mo.open("wb") as file:
            write_mo(file, catalog)


def placeholders(text: str) -> set[str]:
    """The ``{name}`` a text fills in; ``{{`` and ``}}`` are literal braces."""
    return set(PLACEHOLDER.findall(text.replace("{{", "").replace("}}", "")))


def translations_of(message: Message) -> Iterable[str]:
    return message.string if isinstance(message.string, (list, tuple)) else [message.string]


def problems(catalog: Catalog, template: Catalog) -> list[str]:
    """What keeps ``catalog`` from being complete: texts the code has that it lacks,
    texts without a translation or marked as doubtful, and translations whose
    placeholders differ from their Spanish ones: an unknown one breaks the sentence when
    it is filled in, and a missing one leaves out what the sentence was about."""
    found = []
    for message in template:
        if message.id and catalog.get(message.id, message.context) is None:
            found.append(f"falta en el catálogo (extract): {message.id!r}")
    for message in catalog:
        if not message.id:
            continue
        name = message.id if isinstance(message.id, str) else message.id[0]
        texts = list(translations_of(message))
        if not all(texts):
            found.append(f"sin traducir: {name!r}")
            continue
        if message.fuzzy:
            found.append(f"dudosa (fuzzy): {name!r}")
        plural = isinstance(message.id, (list, tuple))
        wanted = placeholders(name) | (placeholders(message.id[1]) if plural else set())
        for form, text in enumerate(texts):
            have = placeholders(text)
            # The singular of a plural may leave the number out: «one installment».
            if not have <= wanted or (have != wanted and not (plural and form == 0)):
                found.append(f"marcadores distintos: {name!r} → {text!r}")
    return found


def check() -> list[str]:
    template = extracted()
    return [
        f"{language}: {problem}"
        for language in LANGUAGES
        for problem in problems(read_catalog(language), template)
    ]


REVIEW_STYLE = """
body { font: 14px/1.45 "Segoe UI", sans-serif; margin: 24px; color: #222; }
h2 { margin-top: 32px; font-size: 16px; border-bottom: 1px solid #ccc; }
table { border-collapse: collapse; width: 100%; }
td { vertical-align: top; padding: 6px 8px; border-bottom: 1px solid #eee; width: 50%; }
.shots img { width: 49%; border: 1px solid #ddd; margin: 4px 0; }
"""


def screen_of(message: Message) -> str:
    """Where a text shows, by the first file that uses it: "pages/budgets_page"."""
    path = Path(sorted(message.locations)[0][0])
    parts = path.with_suffix("").parts
    return "/".join(parts[parts.index("nodus") + 1 :]).removeprefix("ui/")


def review(language: str, shots: Path | None) -> str:
    """A page with every text of the catalog, Spanish beside ``language``, grouped by the
    screen that shows it; with ``shots`` (the ``es`` and ``en`` folders of
    ``screenshot.py``), each capture in both languages at the end."""
    screens: dict[str, list[Message]] = {}
    for message in read_catalog(language):
        if message.id:
            screens.setdefault(screen_of(message), []).append(message)
    out = [f"<!doctype html><meta charset=utf-8><title>Nodus: {language}</title>"]
    out.append(f"<style>{REVIEW_STYLE}</style><h1>Nodus en español y {language}</h1>")
    for screen, messages in sorted(screens.items()):
        out.append(f"<h2>{html.escape(screen)}</h2><table>")
        for message in messages:
            source = message.id if isinstance(message.id, str) else " | ".join(message.id)
            target = translations_of(message)
            out.append(
                f"<tr><td>{html.escape(source)}</td><td>{html.escape(' | '.join(target))}</td></tr>"
            )
        out.append("</table>")
    if shots is not None:
        out.append("<h2>Capturas</h2>")
        for spanish in sorted((shots / "es").glob("*-light.png")):
            other = shots / language / spanish.name
            out.append(
                f"<div class=shots><p>{spanish.stem}</p>"
                f"<img src='{spanish.as_uri()}'> <img src='{other.as_uri()}'></div>"
            )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # the texts have accents; Windows' console not
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["extract", "compile", "check", "review"])
    parser.add_argument("--out", type=Path, default=Path("screenshots/traduccion.html"))
    parser.add_argument("--shots", type=Path, help="screenshots taken in es/ and en/")
    args = parser.parse_args(argv)
    command = args.command
    if command == "extract":
        extract()
    elif command == "compile":
        compile_catalogs()
    elif command == "review":
        args.out.parent.mkdir(parents=True, exist_ok=True)
        shots = args.shots.resolve() if args.shots else None
        args.out.write_text(review(LANGUAGES[0], shots), encoding="utf-8")
        print(f"Revisión escrita en {args.out}")
    else:
        found = check()
        for problem in found:
            print(problem)
        if found:
            return 1
        print("El catálogo está completo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
