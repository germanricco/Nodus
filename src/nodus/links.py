"""The web addresses Nodus links to, kept in one place."""

from urllib.parse import urlencode

from nodus import __version__

REPOSITORY = "germanricco/Nodus"
REPOSITORY_URL = f"https://github.com/{REPOSITORY}"
DONATE_URL = "https://cafecito.app/germanricco"

# A Google Form, which asks for no account. Its "Versión" field comes filled in, so
# every comment says which Nodus it is about.
_FEEDBACK_FORM = (
    "https://docs.google.com/forms/d/e/"
    "1FAIpQLSev7Wu3txRIEU81y7N6GUS1kQEljgitJNdeRhpLfZYiTgALcA/viewform"
)
_FEEDBACK_VERSION_FIELD = "entry.462321622"


def feedback_url(version: str = __version__) -> str:
    """The comments form, with ``version`` already in its "Versión" field."""
    return f"{_FEEDBACK_FORM}?{urlencode({'usp': 'pp_url', _FEEDBACK_VERSION_FIELD: version})}"
