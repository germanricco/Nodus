"""The web addresses Nodus links to, kept in one place."""

from dataclasses import dataclass
from urllib.parse import urlencode

from nodus import __version__
from nodus.i18n import Language, current_language

REPOSITORY = "germanricco/Nodus"
REPOSITORY_URL = f"https://github.com/{REPOSITORY}"
# The page of the newest release, with its installer.
DOWNLOAD_URL = f"{REPOSITORY_URL}/releases/latest"
DONATE_URL = "https://cafecito.app/germanricco"
# What Nodus asks for by itself: the newest version (``release_file_url``), and the
# exchange rates.
DOLARAPI_URL = "https://dolarapi.com/v1/dolares"
QUOTES_URL = "https://dolarapi.com/v1/cotizaciones"


def release_page(version: str) -> str:
    """The page of the release of ``version``, with its notes and its installers."""
    return f"{REPOSITORY_URL}/releases/tag/v{version}"


def release_file_url(name: str, version: str | None = None) -> str:
    """A file attached to the release of ``version``, or to the newest one if None: a
    plain download, which GitHub does not limit as it limits its API."""
    if version is None:
        return f"{REPOSITORY_URL}/releases/latest/download/{name}"
    return f"{REPOSITORY_URL}/releases/download/v{version}/{name}"


# A Google Form, which asks for no account. Its "Versión" field comes filled in, so
# every comment says which Nodus it is about. Each language has its own copy of the form,
# and a copy has its own field ids, read from the form's public page.


@dataclass(frozen=True)
class FeedbackForm:
    """One copy of the comments form, with the ids of the fields Nodus fills in."""

    url: str
    version_field: str
    kind_field: str  # «¿Qué querés contarnos?»
    detail_field: str  # «Contanos con detalle»
    bug_kind: str  # the kind field's option for an error, word for word


FEEDBACK_FORMS = {
    Language.SPANISH: FeedbackForm(
        url="https://docs.google.com/forms/d/e/"
        "1FAIpQLSev7Wu3txRIEU81y7N6GUS1kQEljgitJNdeRhpLfZYiTgALcA/viewform",
        version_field="entry.462321622",
        kind_field="entry.1417373821",
        detail_field="entry.1232171367",
        bug_kind="Algo no funciona",
    ),
}
# Longer links can be cut short on their way to the browser.
MAX_URL_LENGTH = 2000


def feedback_form() -> FeedbackForm:
    """The form in the language Nodus is in; the Spanish one for a language without its
    own copy yet."""
    return FEEDBACK_FORMS.get(current_language(), FEEDBACK_FORMS[Language.SPANISH])


def feedback_url(version: str = __version__) -> str:
    """The comments form, with ``version`` already in its "Versión" field."""
    form = feedback_form()
    return _prefilled(form, {form.version_field: version})


def bug_report_url(report: str, version: str = __version__) -> str:
    """The comments form filled in as a report of an error: its "something is wrong"
    kind, the ``report`` as the detail, and the version. The user reads it before
    sending it."""
    form = feedback_form()
    return _prefilled(
        form,
        {
            form.kind_field: form.bug_kind,
            form.detail_field: report,
            form.version_field: version,
        },
    )


def _prefilled(form: FeedbackForm, fields: dict[str, str]) -> str:
    return f"{form.url}?{urlencode({'usp': 'pp_url', **fields})}"
