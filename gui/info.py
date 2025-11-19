from tkinter import constants, ttk


class InfoFrame(ttk.Labelframe):
    cmdr: ttk.Label
    ship: ttk.Label
    location: ttk.Label

    def __init__(
        self,
        parent,
        ship: str | None = None,
        location: dict[str, str] | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(parent, *args, **kwargs)
        self.config(text="Status")
        self.ship = ttk.Label(self, text=f"Ship: {ship or '<unknown>'}")
        self.location = ttk.Label(
            self, text=f"Location: {self.format_location(location or {})}"
        )
        self.ship.pack(padx=5, anchor=constants.W, side=constants.TOP)
        self.location.pack(padx=5, anchor=constants.W, side=constants.TOP)

    @staticmethod
    def format_location(location: dict[str, str] | None) -> str:
        if not location or "system" not in location:
            return "<unknown>"

        parts = [f"  ├ System: {location['system']}"]

        # Always show system

        # Optional fields
        if "body" in location:
            parts.append(f"  ├ Body: {location['body']}")
        if "station" in location:
            parts.append(f"  └ Station: {location['station']}")
        else:
            # If there's no station but body exists, fix the last prefix:
            if parts[-1].startswith("  ├"):
                parts[-1] = parts[-1].replace("├", "└", 1)

        return "\n" + "\n".join(parts)

    def update_cmdr(self, ship: str | None, location: dict[str, str] | None) -> None:
        self.ship.config(text=f"Ship: {ship or '<unknown>'}")
        self.location.config(text=f"Location: {self.format_location(location or {})}")
