import pathlib
import ctypes
from ctypes import wintypes
from typing import Any
from uuid import UUID
import logging
import tomlkit
from readerwriterlock.rwlock import RWLockRead
from tomlkit import TOMLDocument, table

import _version

appname = "hugh"

logger = logging.getLogger(__name__)


def appversion() -> str:
    return _version.__version__


SHGetKnownFolderPath = ctypes.windll.shell32.SHGetKnownFolderPath
SHGetKnownFolderPath.argtypes = [
    ctypes.POINTER(ctypes.c_byte * 16),
    wintypes.DWORD,
    wintypes.HANDLE,
    ctypes.POINTER(ctypes.c_wchar_p),
]
SHGetKnownFolderPath.restype = ctypes.c_long

KF_FLAG_DEFAULT = 0

LOCALAPPDATA = "{F1B32785-6FBA-4FCF-9D55-7B8E7F157091}"
SAVEDGAMES = "{4C5C32FF-BB9D-43b0-B5B4-2D72E54EAAA4}"
DOCUMENTS = "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}"


def known_folder_path(folderid: str) -> pathlib.Path:
    """
    folderid: string UUID of the Known Folder, e.g.,
    - LocalAppData: "{F1B32785-6FBA-4FCF-9D55-7B8E7F157091}"
    - SavedGames:  "{4C5C32FF-B7D2-4F73-9C14-5FC2318AC7E}"
    """
    fid = UUID(folderid)
    fid_bytes = (ctypes.c_byte * 16).from_buffer_copy(fid.bytes_le)
    out_path = ctypes.c_wchar_p()
    hr = SHGetKnownFolderPath(
        ctypes.byref(fid_bytes), KF_FLAG_DEFAULT, 0, ctypes.byref(out_path)
    )
    if hr != 0:
        raise OSError(f"SHGetKnownFolderPath failed with HRESULT 0x{hr:X}")
    path = pathlib.Path(out_path.value)
    ctypes.windll.Ole32.CoTaskMemFree(out_path)
    return path


class Config:
    app_dir_path: pathlib.Path
    default_journal_path: pathlib.Path
    plugins_dir: pathlib.Path

    lock: RWLockRead

    def __init__(self, filename: str | None = None):
        self.lock = RWLockRead()

        if local_appdata := known_folder_path(LOCALAPPDATA):
            self.app_dir_path = local_appdata / appname

        self.app_dir_path.mkdir(exist_ok=True)

        self.plugins_dir = self.app_dir_path / "plugins"
        self.plugins_dir.mkdir(exist_ok=True)

        self.default_journal_path = (
            known_folder_path(SAVEDGAMES) / "Frontier Developments" / "Elite Dangerous"
        )

        self.filename = self.app_dir_path / "config.toml"
        if filename is not None:
            self.filename = pathlib.Path(filename)

        self.filename.parent.mkdir(exist_ok=True, parents=True)
        self.config = tomlkit.document()
        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                self.config = tomlkit.load(f)
        except FileNotFoundError:
            pass

    def plugin_config(self, name: str):
        return PluginConfig(self.config, name)

    @property
    def default_journal_dir(self) -> pathlib.Path:
        return self.default_journal_path

    def get_list(self, key: str, *, section: str | None = None) -> list[Any]:
        return self.__get(key, section=section)

    def get_dict(self, key: str, *, section: str | None = None) -> dict[str, Any]:
        return self.__get(key, section=section)

    def get_str(
        self, key: str, *, section: str | None = None, default: str | None = None
    ) -> str:
        return str(self.__get(key, section=section, default=default))

    def __get(
        self, key: str, *, section: str | None = None, default: str | None = None
    ) -> Any:
        with self.lock.gen_rlock():
            if section is None:
                return self.config.get(key, default)
            else:
                sect = self.config.get(section)
                if sect is None:
                    return default
                return sect.get(key, default)

    def set(self, key: str, value: Any, *, section: str | None = None) -> None:
        with self.lock.gen_wlock():
            if section is None:
                self.config.set(key, value)
            else:
                tbl = self.config.get(section)
                if tbl is None:
                    tbl = table()
                    self.config[section] = tbl
            tbl[key] = value

    def add_journal(self, name: str, path: pathlib.Path) -> None:
        with self.lock.gen_wlock():
            journals = self.config.get("journals")

            # If the section disappeared somehow
            if journals is None:
                journals = self.config["journals"] = []

            entry = tomlkit.table()
            entry.add("name", name)
            entry.add("path", str(path))

            journals.append(entry)

    def get_journals(self) -> list:
        with self.lock.gen_rlock():
            return self.config.get(
                "journals", [{"name": "<unknown>", "path": self.default_journal_path}]
            )

    def set_journals(self, new: list) -> None:
        with self.lock.gen_wlock():
            journals = []
            for x in new:
                entry = tomlkit.table()
                entry.update(x)
                journals.append(entry)
            self.config["journals"] = journals

    def save(self) -> None:
        with self.lock.gen_wlock():
            with open(self.filename, "w", encoding="utf-8") as f:
                tomlkit.dump(self.config, f)


class PluginConfig:
    def __init__(self, toml: TOMLDocument, section: str):
        self._toml = toml
        self._section = section

        if section not in self._toml:
            self._toml[section] = table()
        self._tbl = self._toml[section]

    def get(self, key, default=None):
        if key not in self._tbl and default is not None:
            self.set(key, default)
            return default
        if key not in self._tbl:
            return default
        return self._tbl[key]

    def set(self, key, value):
        self._tbl[key] = value

    def delete(self, key):
        if key in self._tbl:
            del self._tbl[key]

    def keys(self):
        return self._tbl.keys()

    def items(self):
        return self._tbl.items()

    def __getitem__(self, key):
        return self._tbl[key]

    def __setitem__(self, key, value):
        self._tbl[key] = value

    def __repr__(self):
        return f"<Config section='{self._section}' keys={list(self._tbl.keys())}>"


config = Config()
