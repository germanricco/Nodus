from urllib.parse import parse_qs, urlparse

from nodus import __version__
from nodus.links import bug_report_url, feedback_url


def test_feedback_form_comes_with_the_version_filled_in():
    query = parse_qs(urlparse(feedback_url()).query)

    assert query == {"usp": ["pp_url"], "entry.462321622": [__version__]}


def test_bug_report_comes_with_kind_detail_and_version_filled_in():
    query = parse_qs(urlparse(bug_report_url("Qué falló\nDónde")).query)

    assert query == {
        "usp": ["pp_url"],
        "entry.1417373821": ["Algo no funciona"],
        "entry.1232171367": ["Qué falló\nDónde"],
        "entry.462321622": [__version__],
    }
