import tkinter as tk
import webbrowser
from tkinter import ttk
from typing import Any, MutableMapping

from api import Config, Journal
from api.gui import ScrollableLabelFrame
from api.plugin import Plugin

from i8ln import _C

import httpx


class RavenPlugin(Plugin):
    config: Config
    base_url: str
    projects: dict[str, dict]
    active: dict[str, Any]
    username: str
    api_key: str
    delivery: ScrollableLabelFrame

    @property
    def name(self) -> str:
        return "Raven Colonial"

    def load(self, config: Config) -> bool:
        self.config = config
        self.base_url = config.get(
            "base_url",
            "https://ravencolonial100-awcbdvabgze4c5cq.canadacentral-01.azurewebsites.net",
        )
        self.username = config.get("username", "")
        self.api_key = config.get("api_key", "")
        res = httpx.get(f"{self.base_url}/api/cmdr/{self.username}/active")
        projects = res.json()
        self.projects = {f"{x['systemName']} - {x['buildName']}": x for x in projects}
        return True

    def reload(self, config: Config) -> bool:
        self.config = config
        return True

    @staticmethod
    def commodity(name: str) -> str:
        return name[1:-6].lower()

    def journal_event(self, journal: Journal, entry: MutableMapping[str, Any] | None):
        if entry is None:
            return

        if entry["event"] == "ColonisationContribution":
            contributions = {}
            for x in entry["Contributions"]:
                name = self.commodity(x["Name"])
                amount = x["Amount"]
                contributions[name] = amount
                self.active["commodities"][name] -= amount
            httpx.post(
                f"{self.base_url}/api/project/{self.active['buildId']}/contribute/{journal.cmdr}",
                json=contributions,
            )
            self.update_required()

    def update_required(self):
        for widget in self.delivery.inner.winfo_children():
            widget.destroy()

        # Add labels
        for k, v in self.active["commodities"].items():
            if v > 0:
                ttk.Label(self.delivery.inner, text=f"{_C(k)}: {v}").pack(
                    anchor="w", pady=2
                )

    def info_screen(self, notebook: ttk.Notebook, frame: tk.Frame):
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        label = ttk.Label(frame, text="Projects:")
        label.grid(row=0, column=0, padx=4, pady=4, sticky="w")

        combo = ttk.Combobox(frame, values=list(self.projects.keys()))
        combo.grid(row=0, column=1, padx=4, pady=4, sticky="ew")

        self.delivery = ScrollableLabelFrame(frame, text="Required Cargo")
        self.delivery.grid(row=1, column=0, columnspan=2, padx=4, pady=4, sticky="nsew")

        # --- Update your project selection callback ---
        def selected_project(event):
            # Clear previous labels
            for widget in self.delivery.inner.winfo_children():
                widget.destroy()

            self.active = self.projects[combo.get()]

            # Add labels
            for k, v in self.active["commodities"].items():
                if v > 0:
                    ttk.Label(self.delivery.inner, text=f"{_C(k)}: {v}").pack(
                        anchor="w", pady=2
                    )

        combo.bind("<<ComboboxSelected>>", selected_project)

    def config_screen(self, frame: tk.Frame, config: Config) -> None:
        # Link row
        link_frame = ttk.Frame(frame)
        link_frame.grid(row=0, column=0, columnspan=3, sticky="we", padx=0)
        ttk.Label(link_frame, text="Get your API key at: ").pack(side="left")
        link = ttk.Label(
            link_frame,
            text="https://ravencolonial.com/user",
            foreground="blue",
            cursor="hand2",
            underline=True,
        )
        link.bind(
            "<Button-1>",
            lambda e: webbrowser.open_new_tab("https://ravencolonial.com/user"),
        )
        link.pack(side="left")

        # API Key row
        ttk.Label(frame, text="API Key:").grid(row=1, column=0, sticky="w")

        key = tk.StringVar(frame)
        key.set(self.config.get("api_key", default=""))

        key_entry = ttk.Entry(frame, textvariable=key, width=40)
        key_entry.grid(row=1, column=1, sticky="we", padx=(0, 5))

        button = ttk.Button(frame, text="Check")
        button.grid(row=1, column=2, sticky="e")

        # Username row
        username_label = ttk.Label(
            frame, text=f"Username: {self.config.get('username', '<none>')}"
        )
        username_label.grid(row=2, column=0, pady=(10, 0), sticky="w")

        def on_click(event: tk.Event) -> None:
            res = httpx.get(f"{self.base_url}/api/cmdr", headers={"rcc-key": key.get()})
            if res.status_code == 200:
                json = res.json()
                self.config.set("username", json["displayName"])
                self.config.set("api_key", key.get())
                self.username = json["displayName"]
                self.api_key = key.get()
                username_label.configure(text=f"Username: {json['displayName']}")
            else:
                username_label.configure(
                    text=f"API responded with {res.status_code} {res.text}"
                )

        button.bind("<Button-1>", on_click)
