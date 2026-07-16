"""Small helpers for pipeline script steps.

`job_runner` still owns orchestration, queueing, DB status, and pause/cancel
logic. This module owns the repeatable mechanics of running standalone scripts
and writing step logs.
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
SCRIPTS = BASE_DIR / "scripts"
PYTHON = sys.executable


@dataclass(frozen=True)
class ScriptResult:
    ok: bool
    output: str
    command: list[str]


@dataclass(frozen=True)
class PipelineContext:
    job_id: int
    job_key: str
    log_path: Path


class PipelineStepRunner:
    def __init__(self, scripts_dir: Path = SCRIPTS, python: str = PYTHON, timeout: int = 1500):
        self.scripts_dir = scripts_dir
        self.python = python
        self.timeout = timeout

    def run_script(self, script: str, job_key: str, extra: list[str] | None = None, log_path: Path | None = None) -> ScriptResult:
        cmd = [self.python, str(self.scripts_dir / script), job_key, *(extra or [])]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.timeout,
        )
        output = result.stdout + result.stderr
        if log_path:
            self.append_log(log_path, f"\n=== {script} ===\n{output}\n")
        return ScriptResult(result.returncode == 0, output, cmd)

    @staticmethod
    def append_log(log_path: Path, text: str) -> None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(text)

    def run_nonfatal(self, script: str, job_key: str, extra: list[str] | None, log_path: Path, warning: str) -> ScriptResult:
        result = self.run_script(script, job_key, extra, log_path)
        if not result.ok:
            self.append_log(log_path, f"\n[WARN] {warning}:\n{result.output[-800:]}\n")
        return result
