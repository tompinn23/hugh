import pathlib
from typing import Any, Protocol


class CAPI(Protocol):
    def profile(self) -> dict[str, Any]: ...
    def fleet_carrier(self) -> dict[str, Any]: ...


class Journal(Protocol):
    """
    Journal interface, the internal journal used by vase does provide more information,
    if and when the information is required by a plugin this class will be extended.
    """

    @property
    def directory(self) -> pathlib.Path: ...

    @property
    def cmdr(self) -> str: ...

    @property
    def state(self) -> dict: ...
