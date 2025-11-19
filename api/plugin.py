import tkinter
from concurrent.futures import Future
from tkinter import ttk
from typing import (
    Any,
    MutableMapping,
    Protocol,
    runtime_checkable,
    ParamSpec,
    TypeVar,
    Callable,
)

from .config import Config
from .journal import CAPI, Journal


_P = ParamSpec("_P")
_R = TypeVar("_R")


class WorkPool(Protocol):
    """
    A protocol describing an asynchronous work scheduler that can execute
    callables in a background thread or worker pool and return a ``Future`` for
    their result.

    The ``WorkPool`` interface provides two methods:

    ``run`` — the full-featured submission method that optionally integrates
    with Tkinter widgets and UI-safe callbacks.

    ``run0`` — a convenience wrapper for submitting work without a widget or
    callback.
    """

    def run(
        self,
        widget: tkinter.Misc,
        callback: Callable[[_R], None],
        func: Callable[_P, _R],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> Future[_R]:
        """
        Schedule a callable to be executed asynchronously.

        Parameters
        ----------
        widget:
            A Tkinter widget. The implementationw will use it to ensure that the ``callback`` is invoked
            in the Tkinter main thread via ``widget.after``.

        callback:
            A function taking the result of ``func`` as its single argument.
            It will be called once the task completes in the Tkinter
            main loop. If ``None``, no callback is
            invoked.

        func:
            The callable to execute in the worker pool.

        *args, **kwargs:
            Arguments to pass to ``func``.

        Returns
        -------
        Future[_R]
            A ``Future`` representing the eventual result of the computation.
        """
        ...

    def run0(
        self, func: Callable[_P, _R], *args: _P.args, **kwargs: _P.kwargs
    ) -> Future[_R]:
        """
        Schedule a callable to be executed asynchronously without any UI
        integration or completion callback.

        This is equivalent to calling ``run(None, None, func, *args, **kwargs)``.

        Parameters
        ----------
        func:
            The callable to execute in the worker pool.

        *args, **kwargs:
            Arguments to pass to ``func``.

        Returns
        -------
        Future[_R]
            A ``Future`` representing the result of the computation.
        """
        ...


@runtime_checkable
class ConfigurableScreen(Protocol):
    def config_screen(self, frame: tkinter.Frame, config: Config) -> None: ...


@runtime_checkable
class InfoScreen(Protocol):
    def info_screen(
        self, notebook: ttk.Notebook, frame: tkinter.Frame, pool: WorkPool
    ) -> None: ...


class Plugin:
    @property
    def internal_name(self) -> str:
        return self.name.lower().replace(" ", "_")

    @property
    def name(self) -> str: ...

    def load(self, config: Config) -> bool: ...

    def reload(self, config: Config) -> bool: ...

    def journal_event(
        self,
        pool: WorkPool,
        journal: Journal,
        capi: CAPI,
        entry: MutableMapping[str, Any] | None,
    ): ...
