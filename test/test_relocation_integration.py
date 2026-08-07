from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
class RelocationIntegrationTests(unittest.TestCase):
    def test_runtime_python_files_do_not_reference_legacy_host(self):
        runtime_files = list(PROJECT_ROOT.glob("*.py"))
        combined = "\n".join(path.read_text(encoding="utf-8") for path in runtime_files)

        self.assertNotIn("API-BLENDER", combined)
        self.assertNotIn("cowork_feature", combined)
        self.assertNotIn("app_main.py", combined)
        self.assertNotIn("run_cowork_agent", combined)
        self.assertFalse((PROJECT_ROOT / "runtime.py").exists())

    def test_installed_bootstrap_imports_outside_source_checkout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run(
                [sys.executable, "-c", "import AI_DEV_COWORKER.cowork"],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
