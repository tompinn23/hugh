import logging
import re
import tkinter as tk
import webbrowser
from collections import defaultdict
from tkinter import ttk
from typing import Any, MutableMapping

from api import Config, Journal
from api.gui import ScrollableLabelFrame
from api.journal import CAPI
from api.plugin import Plugin, WorkPool

from i8ln import _C

import httpx


logger = logging.getLogger()


class RavenPlugin(Plugin):
    config: Config
    base_url: str
    projects: dict[str, dict]
    fleet_carriers: dict[str, dict]
    active: dict[str, Any]
    username: str
    api_key: str
    delivery: ScrollableLabelFrame
    market_id: int = 0
    market_updates: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    _RE_COMMODITY = re.compile(R"(?:\$|)([a-zA-Z]+)(?:_name;|)")

    @property
    def name(self) -> str:
        return "Raven Colonial"

    def load(self, config: Config) -> bool:
        self.config = config
        self.base_url = config.get(
            "base_url",
            "https://ravencolonial100-awcbdvabgze4c5cq.canadacentral-01.azurewebsites.net",
        )
        self.projects = {}
        self.username = config.get("username", "")
        self.api_key = config.get("api_key", "")

        if self.api_key != "":
            res = httpx.get(f"{self.base_url}/api/cmdr/{self.username}/active")
            if res.status_code == 200:
                projects = res.json()
                self.projects = {
                    f"{x['systemName']} - {x['buildName']}": x for x in projects
                }
            res = httpx.get(f"{self.base_url}/api/cmdr/{self.username}/fc/all")
            if res.status_code == 200:
                data = res.json()
                self.fleet_carriers = {x["marketId"]: x for x in data}

        return True

    def reload(self, config: Config) -> bool:
        self.config = config
        return True

    @staticmethod
    def commodity(name: str) -> str:
        return RavenPlugin._RE_COMMODITY.fullmatch(name).group(1)

    def update_fc(self, pool: WorkPool, market_id):
        def do_work():
            logger.debug(
                f"Updating fleet carrier {market_id} with {self.market_updates[market_id]}"
            )
            res = httpx.patch(
                f"{self.base_url}/api/fc/{self.market_id}/cargo",
                json=self.market_updates[market_id],
            )
            if res.status_code != 200:
                logger.error(
                    f"Failed to update commodities for fleet carrier {res.text}"
                )
            self.market_updates.clear()

        pool.run0(do_work)

    def journal_event(
        self,
        pool: WorkPool,
        journal: Journal,
        capi: CAPI,
        entry: MutableMapping[str, Any] | None,
    ):
        if entry is None:
            return

        if entry["event"] == "Undocked":
            if self.market_id in self.fleet_carriers:
                logger.info(
                    f"Took off from on related FC {self.fleet_carriers[self.market_id]['displayName']}"
                )
            self.update_fc(self.market_id)
            self.market_id = 0

        if entry["event"] == "Docked":
            if self.market_id != 0:
                self.update_fc(self.market_id)
            self.market_id = entry["MarketID"]
            if self.market_id in self.fleet_carriers:
                logger.info(
                    f"Landed on related FC {self.fleet_carriers[self.market_id]['displayName']}"
                )

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

        if entry["event"] == "MarketSell":
            if self.market_id in self.fleet_carriers:
                name = self.commodity(entry["Type"])
                amount = entry["Count"]
                self.market_updates[self.market_id][name] += amount

        if entry["event"] == "MarketBuy":
            if self.market_id in self.fleet_carriers:
                name = self.commodity(entry["Type"])
                amount = entry["Count"]
                self.market_updates[self.market_id][name] -= amount

        if entry["event"] == "CargoTransfer":
            for x in entry["Transfers"]:
                name = self.commodity(x["Type"])
                amount = x["Count"]
                direction = x["Direction"]
                if direction == "tocarrier":
                    self.market_updates[self.market_id][name] += amount
                elif direction == "toship":
                    self.market_updates[self.market_id][name] -= amount

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
                res = httpx.get(f"{self.base_url}/api/cmdr/{self.username}/active")
                if res.status_code == 200:
                    projects = res.json()
                    self.projects = {
                        f"{x['systemName']} - {x['buildName']}": x for x in projects
                    }
            else:
                username_label.configure(
                    text=f"API responded with {res.status_code} {res.text}"
                )

        button.bind("<Button-1>", on_click)
