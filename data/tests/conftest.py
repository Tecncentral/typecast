import os

import pytest


@pytest.fixture(autouse=True)
def _default_vexcel_caps(monkeypatch):
    """Budget tests check the documented default caps; a machine's raised overrides must not leak in."""
    for name in [n for n in os.environ if n.startswith("TYPECAST_VEXCEL_")]:
        monkeypatch.delenv(name)
