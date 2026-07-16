import tempfile
import unittest
from pathlib import Path

from web.pipeline_steps import PipelineStepRunner


class PipelineStepRunnerTest(unittest.TestCase):
    def test_run_nonfatal_logs_warning(self):
        with tempfile.TemporaryDirectory() as td:
            scripts = Path(td) / "scripts"
            scripts.mkdir()
            script = scripts / "fail.py"
            script.write_text("import sys\nprint('boom')\nsys.exit(2)\n", encoding="utf-8")
            log = Path(td) / "run.log"

            runner = PipelineStepRunner(scripts_dir=scripts, python="python", timeout=30)
            result = runner.run_nonfatal("fail.py", "job", [], log, "failed softly")

            self.assertFalse(result.ok)
            text = log.read_text(encoding="utf-8")
            self.assertIn("boom", text)
            self.assertIn("failed softly", text)


if __name__ == "__main__":
    unittest.main()
