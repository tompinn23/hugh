import tkinter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, Future
from typing import ParamSpec, TypeVar

_P = ParamSpec("_P")
_R = TypeVar("_R")


class WorkPool:
    def __init__(self, num: int = 4):
        self.threadpool = ThreadPoolExecutor(num, "hugh-worker")

    def run0(
        self, func: Callable[_P, _R], *args: _P.args, **kwargs: _P.kwargs
    ) -> Future[_R]:
        return self.threadpool.submit(func, *args, **kwargs)

    def run(
        self,
        widget: tkinter.Misc,
        callback: Callable[[_R], None],
        func: Callable[_P, _R],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> Future[_R]:
        future: Future[_R] = self.threadpool.submit(func, *args, **kwargs)

        def _done(f: Future[_R]) -> None:
            result = f.result()
            if callback is not None:
                widget.after(0, callback, result)

        future.add_done_callback(_done)
        return future
