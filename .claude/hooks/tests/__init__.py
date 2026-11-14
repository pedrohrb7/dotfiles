"""Hermetic environment for the agent-audit hook test suite.

Runs before any test module imports the hook: `METRICS_DIR` is read from the environment when
agent-audit.py / agent-metrics.py are imported, so it must be redirected here.
"""
import atexit
import os
import shutil
import tempfile

# A test that forgets to redirect the metrics writes here, never to ~/.claude/metrics.
_METRICS_DIR = tempfile.mkdtemp(prefix="agent-audit-tests-metrics-")
os.environ["AGENT_AUDIT_DIR"] = _METRICS_DIR
atexit.register(shutil.rmtree, _METRICS_DIR, ignore_errors=True)

# git_root() must depend only on the path (the suite may run from inside a git hook).
for _var in (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_CEILING_DIRECTORIES",
):
    os.environ.pop(_var, None)

# In-process tests must not read the user's or the system git config either (HookProcess does the
# same for the hook copy). `git init` needs no identity; no test commits.
os.environ["GIT_CONFIG_GLOBAL"] = os.devnull
os.environ["GIT_CONFIG_NOSYSTEM"] = "1"


def load_tests(loader, standard_tests, pattern):
    """Discovery hook of the package: one `ForkedSuite` for the whole suite instead of one per module (see
    `_support.package_suite`), so the workers never idle at the end of a module."""
    from ._support import package_suite
    return package_suite(loader, __name__, __file__, pattern or "test*.py")
