"""Run the credential-free integration gate from any working directory."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
env = {
    **os.environ,
    "TYPECAST_USE_MOCKS": "1",
    "TYPECAST_ENGINE": "fixed",
    "TYPECAST_ENABLE_MODEL_PARSE": "0",
    "TYPECAST_ENABLE_VISION_RERANK": "0",
    "TYPECAST_ALLOW_VISION_UPLOAD": "0",
    "LANGSMITH_TRACING": "false",
    "LANGCHAIN_TRACING_V2": "false",
    **{key: "" for key in (
        "LLM_API_KEY", "VISION_API_KEY", "FALLBACK_API_KEY", "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY", "LANGSMITH_API_KEY", "LANGCHAIN_API_KEY",
    )},
}
result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, env=env)
if result.returncode:
    raise SystemExit(result.returncode)
subprocess.run([sys.executable, str(ROOT / "scripts/smoke.py")], cwd=ROOT, env=env, check=True)
subprocess.run([sys.executable, str(ROOT / "scripts/e2e.py")], cwd=ROOT, env=env, check=True)
with tempfile.TemporaryDirectory(prefix="typecast-eval-") as directory:
    subprocess.run([
        sys.executable, str(ROOT / "agent/eval/run_eval.py"), "--mode", "mock",
        "--output", str(Path(directory) / "eval.md"),
    ], cwd=ROOT, env=env, check=True)
