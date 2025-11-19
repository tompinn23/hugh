import tkinter
from concurrent.futures import Future
from tkinter import ttk
from typing import Any, MutableMapping, Protocol, runtime_checkable, ParamSpec, TypeVar, Callable

from .config import Config
from .journal import Journal


_P = ParamSpec("_P")
_R = TypeVar("_R")


class WorkPool(Protocol):
    def run(self, widget: tkinter.Misc, callback: Callable[[_R], None], func: Callable[_P, _R], *args: _P.args,
            **kwargs: _P.kwargs) -> Future[_R]: ...


@runtime_checkable
class ConfigurableScreen(Protocol):
    def config_screen(self, frame: tkinter.Frame, config: Config) -> None: ...


@runtime_checkable
class InfoScreen(Protocol):
    def info_screen(self, notebook: ttk.Notebook, frame: tkinter.Frame, pool: WorkPool) -> None: ...

class Plugin:
    @property
    def internal_name(self) -> str:
        return self.name.lower().replace(" ", "_")

    @property
    def name(self) -> str: ...

    def load(self, config: Config) -> bool: ...

    def reload(self, config: Config) -> bool: ...

    def journal_event(
            self, pool: WorkPool, journal: Journal, entry: MutableMapping[str, Any] | None
    ): ...
