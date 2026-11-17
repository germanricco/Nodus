"""The web addresses Nodus links to, kept in one place."""

from urllib.parse import urlencode

from nodus import __version__

REPOSITORY = "germanricco/Nodus"
REPOSITORY_URL = f"https://github.com/{REPOSITORY}"
DONATE_URL = "https://cafecito.app/germanricco"
# What Nodus asks for by itself: the newest version, and the exchange rates.
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
DOLARAPI_URL = "https://dolarapi.com/v1/dolares"
QUOTES_URL = "https://dolarapi.com/v1/cotizaciones"

# A Google Form, which asks for no account. Its "Versión" field comes filled in, so
# every comment says which Nodus it is about. The fields' ids are read from the form's
# public page.
_FEEDBACK_FORM = (
    "https://docs.google.com/forms/d/e/"
    "1FAIpQLSev7Wu3txRIEU81y7N6GUS1kQEljgitJNdeRhpLfZYiTgALcA/viewform"
)
_FEEDBACK_VERSION_FIELD = "entry.462321622"
_FEEDBACK_KIND_FIELD = "entry.1417373821"  # «¿Qué querés contarnos?»
_FEEDBACK_DETAIL_FIELD = "entry.1232171367"  # «Contanos con detalle»
BUG_KIND = "Algo no funciona"  # one of the kind field's options, word for word
# Longer links can be cut short on their way to the browser.
MAX_URL_LENGTH = 2000


def feedback_url(version: str = __version__) -> str:
    """The comments form, with ``version`` already in its "Versión" field."""
    return _prefilled({_FEEDBACK_VERSION_FIELD: version})


def bug_report_url(report: str, version: str = __version__) -> str:
    """The comments form filled in as a report of an error: «Algo no funciona», the
    ``report`` as the detail, and the version. The user reads it before sending it."""
    return _prefilled(
        {
            _FEEDBACK_KIND_FIELD: BUG_KIND,
            _FEEDBACK_DETAIL_FIELD: report,
            _FEEDBACK_VERSION_FIELD: version,
        }
    )


def _prefilled(fields: dict[str, str]) -> str:
    return f"{_FEEDBACK_FORM}?{urlencode({'usp': 'pp_url', **fields})}"
