import gettext
from typing import Callable

LOCALE_DIR = "locales"

_: Callable
_C: Callable


def setup(lang: str = "en"):
    global _, _C
    messages = gettext.translation(
        domain="messages",
        localedir=LOCALE_DIR,
        languages=[lang],
        fallback=True,
    )

    commodity = gettext.translation(
        domain="commodity",
        localedir=LOCALE_DIR,
        languages=[lang],
        fallback=True,
    )

    _ = messages.gettext
    _C = commodity.gettext
