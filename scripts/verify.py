"""Run the credential-free integration gate from any working directory."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
env = {**os.environ, "TYPECAST_USE_MOCKS": "1", "TYPECAST_EVENT_DELAY": "0"}
result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, env=env)
if result.returncode:
    raise SystemExit(result.returncode)
subprocess.run([sys.executable, str(ROOT / "scripts/smoke.py")], cwd=ROOT, env=env, check=True)
