"""Shared loader for the hyphenated hook modules (agent-audit.py, agent-metrics.py, ...)."""
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

HOOKS_DIR = Path(__file__).resolve().parent.parent


def load_hook(file_name: str, module_name: str | None = None) -> ModuleType:
    """Import hooks/<file_name> as a module. Hook main() only runs under __main__, so this is side-effect free."""
    name = module_name or Path(file_name).stem.replace("-", "_")
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, HOOKS_DIR / file_name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
