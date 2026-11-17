"""The report of an unexpected error that the user can send through the comments form.

It says what failed and where in the code, never the user's data: the message is
scrubbed like the log's, and paths start at the ``nodus`` package. It opens in the
browser, where the user reads it, can change it, and sends it only if they want to.
"""

from __future__ import annotations

from nodus.config.logs import HIDDEN, describe, frames, system_line
from nodus.links import MAX_URL_LENGTH, bug_report_url

ASK = "¿Qué estabas haciendo cuando apareció el error?"
WHERE = "Dónde, del último paso al primero:"
MOST_STEPS = 8
# A message this long is cut, when even without steps the link would not fit.
SHORT_MESSAGE = 200


def error_report(error: BaseException, steps: int = MOST_STEPS, message_limit: int = 0) -> str:
    """The report of ``error``: a blank line for the user to tell what they were doing,
    then the error, its last ``steps`` in the code and the system. ``message_limit``,
    when given, cuts the message to that many characters."""
    description = describe(error)
    if message_limit and len(description) > message_limit:
        description = description[:message_limit] + HIDDEN
    lines = [ASK, "", "", "—", f"Error: {description}"]
    innermost = frames(error)[::-1][:steps]
    if innermost:
        lines.append(WHERE)
        lines.extend(f"{step.path}:{step.line} en {step.function}" for step in innermost)
    lines.append(system_line())
    return "\n".join(lines)


def report_url(error: BaseException) -> str:
    """The comments form filled in with the report of ``error``, with as many steps as
    fit in a link the browser takes whole."""
    for steps in range(MOST_STEPS, -1, -1):
        url = bug_report_url(error_report(error, steps))
        if len(url) <= MAX_URL_LENGTH:
            return url
    return bug_report_url(error_report(error, 0, SHORT_MESSAGE))
