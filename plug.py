import importlib
import inspect
import logging
import pathlib
import pkgutil
from typing import Any, MutableMapping, Type, TypeVar


import internal
from api import Journal
from api.plugin import Plugin, WorkPool
from config import Config

_T = TypeVar("_T")

logger = logging.getLogger()


class Loader:
    def __init__(self):
        self.plugins = []
        self.loaded = []

    def load(self, path: pathlib.Path | str | None = None):
        for finder, name, _ in pkgutil.iter_modules(internal.__path__):
            mod = importlib.import_module(f"{internal.__name__}.{name}")
            self._find_attr(mod)

        if path is not None:
            if isinstance(path, str):
                path = pathlib.Path(path)
            for file in path.glob("*/plugin.py"):
                name = file.parent.stem
                spec = importlib.util.spec_from_file_location(name, file)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                self._find_attr(mod)

    def _find_attr(self, mod):
        for attr_name, attr_value in inspect.getmembers(mod):
            if attr_name.startswith("_"):
                continue
            if (
                attr_value.__module__ == mod.__name__
                and inspect.isclass(attr_value)
                and issubclass(attr_value, Plugin)
            ):
                logger.debug(f"Found {attr_name} for plugin {mod.__name__}")
                self.plugins.append(attr_value())
                break  # Stop after finding the first one

    def on_load(self, config: Config) -> None:
        for plugin in self.plugins:
            if plugin.load(config.plugin_config(plugin.internal_name)):
                self.loaded.append(plugin)
            else:
                logger.error(f"Plugin {plugin.name} failed to load")

    def on_reload(self, config: Config) -> None:
        self.loaded.clear()
        for plugin in self.plugins:
            if plugin.reload(config.plugin_config(plugin.internal_name)):
                self.loaded.append(plugin)
            else:
                logger.error(f"Plugin {plugin.name} failed to reload")

    def on_journal_event(
        self, pool: WorkPool, journal: Journal, entry: MutableMapping[str, Any] | None
    ):
        errors = []
        for plugin in self.loaded:
            try:
                plugin.journal_event(pool, journal, entry)
            except Exception as e:
                errors.append(e)
        if errors:
            raise ExceptionGroup("Plugin errors during journal event", errors)

    def get(self, cls: Type[_T]) -> list[_T] | None:
        return [x for x in self.loaded if isinstance(x, cls)]


plug = Loader()
