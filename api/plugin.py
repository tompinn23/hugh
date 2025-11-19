import tkinter
from tkinter import ttk
from typing import Any, MutableMapping, Protocol, runtime_checkable

from .config import Config
from .journal import Journal


@runtime_checkable
class ConfigurableScreen(Protocol):
    def config_screen(self, frame: tkinter.Frame, config: Config) -> None: ...


@runtime_checkable
class InfoScreen(Protocol):
    def info_screen(self, notebook: ttk.Notebook, frame: tkinter.Frame) -> None: ...


class Plugin:
    @property
    def internal_name(self) -> str:
        return self.name.lower().replace(" ", "_")

    @property
    def name(self) -> str: ...

    def load(self, config: Config) -> bool: ...
    def reload(self, config: Config) -> bool: ...

    def journal_event(
        self, journal: Journal, entry: MutableMapping[str, Any] | None
    ): ...
