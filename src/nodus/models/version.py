"""Version numbers of Nodus, as the changelog, the news and the update check read them."""


def parse_version(text: str) -> tuple[int, ...]:
    """ "v0.2.0" or "0.2.0" as (0, 2, 0), so versions compare as numbers ("0.10" > "0.9").

    Raises ValueError if ``text`` is not dot-separated numbers.
    """
    return tuple(int(part) for part in text.strip().removeprefix("v").split("."))
