from urllib.parse import parse_qs, urlparse

from nodus import __version__
from nodus.links import feedback_url


def test_feedback_form_comes_with_the_version_filled_in():
    query = parse_qs(urlparse(feedback_url()).query)

    assert query == {"usp": ["pp_url"], "entry.462321622": [__version__]}
