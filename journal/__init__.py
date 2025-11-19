import json
import pathlib
import queue
from datetime import datetime, timezone
from os.path import isdir
from typing import Any, MutableMapping, Tuple
import tkinter as tk

from .reader import Journal

__all__ = ["Journal", "journals"]


class Monitor:
    journals: dict[pathlib.Path, Journal] = {}
    _queue: queue.Queue[Tuple[Journal, MutableMapping[str, Any] | None]] = queue.Queue()

    def __init__(self):
        pass

    def has_entry(self) -> bool:
        return not self._queue.empty()

    def add_directory(self, master: tk.Tk, path: pathlib.Path):
        if not isdir(path):
            raise ValueError(f"Path {path} is not a directory")
        self.journals[path] = Journal(master, path, self._queue)

    def start(self):
        for x in self.journals.values():
            x.start()

    def get_entry(self) -> Tuple[Journal, MutableMapping[str, Any] | None]:
        if self._queue.empty() and not any(
            [x.game_running() for x in self.journals.values()]
        ):
            return None

        journal, entry = self._queue.get_nowait()

        if not journal.live and entry["event"] not in (None, "Fileheader", "ShutDown"):
            journal.live = True
            entry = journal.synthesize_startup_event()

            self._queue.put((journal, entry))
        elif (
            journal.live
            and entry["event"] == "Music"
            and entry.get("MusicTrack") == "MainMenu"
        ):
            self._queue.put(
                (
                    journal,
                    {
                        "timestamp": datetime.now(timezone.utc),
                        "event": "ShutDown",
                    },
                )
            )

        return journal, entry


journals = Monitor()
