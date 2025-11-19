import tkinter as tk
from tkinter import filedialog, messagebox

from tkinter import ttk
from typing import Iterable

from api import ConfigurableScreen
from capi import CAPIManager, CApi
from config import Config


class InlineEditableTreeview(ttk.Treeview):
    """A Treeview that supports inline editing on double-click."""

    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.editing_entry = None

        self.bind("<Double-1>", self._on_double_click)

    def _on_double_click(self, event):
        # Get column + row clicked
        region = self.identify("region", event.x, event.y)
        if region != "cell":
            return

        row_id = self.identify_row(event.y)
        col_id = self.identify_column(event.x)

        if not row_id:
            return

        # Column index
        col_index = int(col_id.replace("#", "")) - 1

        # Cell bounding box
        x, y, width, height = self.bbox(row_id, col_id)

        # Current value
        old_value = self.item(row_id, "values")[col_index]

        # If editing journal_path: open file dialog instead
        if col_index == 1:
            return
        if col_index == 2:
            new_folder = filedialog.askdirectory(initialdir=old_value)
            if new_folder:
                values = list(self.item(row_id, "values"))
                values[col_index] = new_folder
                self.item(row_id, values=values)
            return

        # Create entry widget for editing
        self.editing_entry = tk.Entry(self, bd=1)
        self.editing_entry.place(x=x, y=y, width=width, height=height)
        self.editing_entry.insert(0, old_value)
        self.editing_entry.focus()

        # When confirmed
        def confirm_edit(event=None):
            new_value = self.editing_entry.get()
            values = list(self.item(row_id, "values"))
            values[col_index] = new_value
            self.item(row_id, values=values)
            self.editing_entry.destroy()
            self.editing_entry = None

        # Cancel
        def cancel_edit(event=None):
            self.editing_entry.destroy()
            self.editing_entry = None

        self.editing_entry.bind("<Return>", confirm_edit)
        self.editing_entry.bind("<Escape>", cancel_edit)
        self.editing_entry.bind("<FocusOut>", confirm_edit)


class JournalLocations(tk.Frame):
    def __init__(self, config: Config, capi: CAPIManager, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.conf = config
        self.capi = capi

        # --- Table setup ---
        columns = ("commander", "capi_status", "journal_path")
        self.tree = InlineEditableTreeview(self, columns=columns, show="headings")
        self.tree.heading("commander", text="Commander")
        self.tree.heading("capi_status", text="CAPI Status")
        self.tree.heading("journal_path", text="Journal Path")

        self.tree.column("commander", width=180, anchor="w")
        self.tree.column("journal_path", width=480, anchor="w")
        self.tree.column("capi_status", width=120, anchor="center")

        self.tree.bind("<<TreeviewSelect>>", self._update_capi_panel)

        for x in self.conf.get_journals():
            name = x["name"]
            path = x["path"]
            capi = "unlinked"
            if self.capi.get_by_cmdr(name) is not None:
                capi = "linked"

            self.tree.insert("", tk.END, values=(name, capi, path))

        self.tree.pack(fill="both", expand=True, pady=10)
        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=5)

        capi_panel = ttk.Frame(self)
        capi_panel.pack(fill="x", pady=5)
        self.capi_panel = capi_panel  # store

        self.capi_commander = ttk.Label(capi_panel, text="Commander: —")
        self.capi_commander.grid(row=0, column=0, sticky="w", padx=4)

        self.capi_status = ttk.Label(capi_panel, text="CAPI Status: —")
        self.capi_status.grid(row=1, column=0, sticky="w", padx=4)

        # Buttons
        self.login_btn = ttk.Button(capi_panel, text="Login", command=self._login)

        self.login_btn.grid(row=0, column=1, padx=5)

        # Initially disabled
        self._set_capi_buttons_state("disabled")

        button_frame = ttk.Frame(self)
        button_frame.pack(fill="x")

        ttk.Button(button_frame, text="Add", command=self.add_entry).pack(
            side="left", padx=5, pady=5
        )
        ttk.Button(button_frame, text="Remove", command=self.remove_entry).pack(
            side="left", padx=5, pady=5
        )

        ttk.Button(button_frame, text="Apply", command=self.save_config).pack(
            side="right", padx=5, pady=5
        )

    def _set_capi_buttons_state(self, state: str):
        self.login_btn["state"] = state

    def _login(self):
        self.capi.login(None, self.update_capi)

    def update_capi(self, capi: CApi):
        cmdr = capi.cmdr
        # Find the matching row in the Treeview
        for row in self.tree.get_children():
            values = list(self.tree.item(row, "values"))
            if values[0] == cmdr:  # commander name matches
                # Update CAPI status column
                values[1] = "linked"  # or "refreshing", "failed", icons, etc.
                self.tree.item(row, values=values)

                # If user has this row selected → update CAPI panel
                if row in self.tree.selection():
                    self._update_capi_panel()

                break

    def _unlink(self):
        pass

    def _update_capi_panel(self, event=None):
        sel = self.tree.selection()
        if not sel:
            self.capi_commander.config(text="Commander: —")
            self.capi_status.config(text="CAPI Status: —")
            self._set_capi_buttons_state("disabled")
            return

        row = sel[0]
        commander, capi_status, path = self.tree.item(row, "values")

        self.capi_commander.config(text=f"Commander: {commander}")
        self.capi_status.config(text=f"CAPI Status: {capi_status}")

        # Update buttons depending on state
        if capi_status == "linked":
            self.login_btn["state"] = "disabled"
        else:
            self.login_btn["state"] = "normal"

    # ----------------------------------------
    def add_entry(self):
        commander = "<unknown>"
        folder = filedialog.askdirectory(title="Select Journal Folder")
        if not folder:
            return
        self.tree.insert("", tk.END, values=(commander, folder))

    # ----------------------------------------
    def remove_entry(self):
        for item in self.tree.selection():
            self.tree.delete(item)

    # ----------------------------------------
    def save_config(self):
        data = []
        for row in self.tree.get_children():
            commander, capi_status, path = self.tree.item(row, "values")
            data.append({"name": commander, "path": path})

        if not data:
            messagebox.showerror("Error", "No entries to save.")
            return

        self.conf.set_journals(data)
        self.conf.save()


class JournalConfigApp(tk.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        config: Config,
        capi: CAPIManager,
        configurables: Iterable,
    ):
        super().__init__(master)
        self.conf: Config = config
        self.capi = capi
        self.title("Elite Dangerous Journal Configuration")
        # self.geometry("700x350")

        self.tabs: ttk.Notebook = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True)

        self.tabs.add(JournalLocations(config, capi, self.tabs), text="General")
        for configurable in configurables:
            frame = tk.Frame(self.tabs)
            configurable.config_screen(
                frame, config.plugin_config(configurable.internal_name)
            )
            self.tabs.add(frame, text=configurable.name)


class ConfigController:
    def __init__(
        self,
        root: tk.Tk,
        config: Config,
        capi: CAPIManager,
        configurables: list[ConfigurableScreen],
    ) -> None:
        self._root = root
        self._config = config
        self._capi = capi
        self.configurables = configurables

    def open_dialog(self) -> None:
        dialog = JournalConfigApp(
            self._root, self._config, self._capi, self.configurables
        )
        dialog.transient(self._root)
        dialog.grab_set()
        dialog.wait_window()
        self._config.save()
