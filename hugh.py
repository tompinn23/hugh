import logging_config


import logging
import sys
import tkinter as tk
from functools import wraps
from tkinter import ttk

import i8ln
from api import ConfigurableScreen, InfoScreen
from capi import CAPIManager
from config import Config, config
from gui.configuration import ConfigController
from gui.info import InfoFrame
from journal import journals
from plug import plug

from worker import WorkPool

if sys.platform == "win32":
    from ctypes import windll

    windll.shcore.SetProcessDpiAwareness(1)

logging_config.setup()

logger = logging.getLogger()


def after_idle(attr=None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(self, *args, **kwargs):
            widget = getattr(self, attr) if attr else self
            widget.after(0, lambda: fn(self, *args, **kwargs))

        return wrapper

    return decorator


class App:
    config: Config
    capi: CAPIManager
    pool: WorkPool
    cmdr_frames: dict[str, InfoFrame]

    def __init__(self, master: tk.Tk, config: Config):
        self.config = config
        self.capi = CAPIManager(master, config)
        self.cmdr_frames = {}
        self.master = master
        self.pool = WorkPool()
        self.menubar = tk.Menu(master)

        config_menu = tk.Menu(self.menubar, tearoff=0)
        config_menu.add_command(label="Settings...", command=self.open_journal_config)
        self.menubar.add_cascade(label="Config", menu=config_menu)

        master.config(menu=self.menubar)
        self.notebook = ttk.Notebook(master)
        self.notebook.pack(fill="both", expand=True)

        self.cmdrs = ttk.Notebook(self.notebook)
        self.cmdrs.pack(fill="both", expand=True)
        self.notebook.add(self.cmdrs, text="Status")

        master.title("Vase")
        master.geometry("500x200")
        self.update_cmdr("unknown")

        # catch any plugin errors before loading capi
        # saves a reauth given we've burnt a refresh token
        plug.load()
        plug.on_load(config)
        self.capi.login_saved(self.config)

        self._config_controller = ConfigController(
            master, config, self.capi, plug.get(ConfigurableScreen)
        )

        plugins = plug.get(InfoScreen)
        for plugin in plugins:
            frame = ttk.Frame(self.notebook)
            plugin.info_screen(self.notebook, frame)
            self.notebook.add(frame, text=plugin.name)

        self.master.bind_all("<<JournalEvent>>", self.journal_event)
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

        journals.add_directory(
            master,
            "C:\\Users\\pooh\\Saved Games\\Frontier Developments\\Elite Dangerous",
        )
        journals.start()

    def on_close(self):
        print("closing...")
        self.capi.save()
        print("done")
        self.master.destroy()

    def reload(self):
        plug.on_reload(self.config)
        self._config_controller = ConfigController(
            self.master, config, plug.get(ConfigurableScreen)
        )

    def update_cmdr(
        self, cmdr: str, ship: str | None = None, location: dict[str, str] | None = None
    ):
        # 1. Remove placeholder if we now have real data
        if cmdr != "unknown" and "unknown" in self.cmdr_frames:
            unknown_frame = self.cmdr_frames.pop("unknown")
            self.cmdrs.forget(unknown_frame)  # remove tab from notebook

        # 2. Create frame if new commander
        if cmdr not in self.cmdr_frames:
            frame = InfoFrame(self.cmdrs, ship, location)
            self.cmdr_frames[cmdr] = frame
            self.cmdrs.add(frame, text=cmdr)
            return

        # 3. Update existing commander frame
        self.cmdr_frames[cmdr].update_cmdr(ship, location)

    def open_journal_config(self):
        if self._config_controller is not None:
            self._config_controller.open_dialog()

    def journal_event(self, event: tk.Event):
        while journals.has_entry():
            journal, entry = journals.get_entry()
            # logger.info(f"Event: {journal.cmdr} {entry}")
            if entry is None:
                return

            if entry["event"] in (
                "LoadGame",
                "Location",
                "FSDjump",
                "Docked",
                "Undocked",
                "ApproachBody",
                "StartUp",
                "LeaveBody",
                "CarrierJump",
            ):
                self.update_cmdr(
                    journal.cmdr,
                    journal.state["ShipType"],
                    {
                        "system": journal.state["SystemName"],
                        "body": journal.state["Body"],
                        "station": journal.state["StationName"],
                    },
                )

            plug.on_journal_event(
                self.pool, journal, self.capi.get_by_fid(journal.fid), entry
            )


if __name__ == "__main__":
    i8ln.setup()
    root = tk.Tk()
    app = App(root, config)
    root.mainloop()
