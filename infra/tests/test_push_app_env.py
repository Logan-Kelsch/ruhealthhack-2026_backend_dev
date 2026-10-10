"""Exercise the env upload with the real CLI's offline JSON validation."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "infra/scripts/push-app-env.sh"


@unittest.skipUnless(shutil.which("aws") and shutil.which("jq"), "Requires AWS CLI and jq")
class PushAppEnvTests(unittest.TestCase):
    def run_upload(self, value, current="", fail=False):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            capture = folder / "capture.json"
            output = folder / "outputs"
            stub = folder / "aws"
            stub.write_text(
                f"#!{sys.executable}\n"
                "import json, os, pathlib, stat, subprocess, sys\n"
                "args = sys.argv[1:]\n"
                "if args[:2] == ['ssm', 'get-parameter']:\n"
                "    print(os.environ['TEST_CURRENT'])\n"
                "    sys.exit(0)\n"
                "assert args[:2] == ['ssm', 'put-parameter']\n"
                "assert os.environ['APP_ENV'] not in args\n"
                "result = subprocess.run([os.environ['TEST_REAL_AWS'], *args, '--generate-cli-skeleton', 'output', '--no-cli-pager'], capture_output=True)\n"
                "sys.stderr.buffer.write(result.stderr)\n"
                "if result.returncode: sys.exit(result.returncode)\n"
                "uri = args[args.index('--cli-input-json') + 1]\n"
                "path = pathlib.Path(uri.removeprefix('file://'))\n"
                "assert stat.S_IMODE(path.stat().st_mode) == 0o600\n"
                "payload = json.loads(path.read_text())\n"
                "assert payload['Value'] == os.environ['APP_ENV']\n"
                "assert payload['Name'] == '/test-env/app-env'\n"
                "assert payload['Type'] == 'SecureString' and payload['Overwrite'] is True\n"
                "pathlib.Path(os.environ['TEST_CAPTURE']).write_text(json.dumps({'path': str(path)}))\n"
                "sys.exit(int(os.environ['TEST_FAIL']))\n"
            )
            stub.chmod(0o755)
            env = {
                **os.environ,
                "PATH": f"{folder}{os.pathsep}{os.environ['PATH']}",
                "APP_ENV": value,
                "PREFIX": "test-env",
                "AWS_REGION": "us-east-1",
                "GITHUB_OUTPUT": str(output),
                "TEST_REAL_AWS": shutil.which("aws"),
                "TEST_CURRENT": current,
                "TEST_CAPTURE": str(capture),
                "TEST_FAIL": str(int(fail)),
            }
            result = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)
            if capture.exists():
                request = Path(json.loads(capture.read_text())["path"])
                self.assertFalse(request.exists(), "Request must be removed on success and failure")
            if value:
                self.assertNotIn(value, result.stdout + result.stderr)
            return result, output.read_text() if output.exists() else "", capture.exists()

    def test_multiline_upload_uses_private_replayable_input(self):
        result, output, uploaded = self.run_upload('DUMMY="quotes and \\slashes"\nSECOND=two\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(uploaded)
        self.assertEqual(output, "changed=true\n")

    def test_unchanged_env_skips_upload(self):
        result, output, uploaded = self.run_upload("DUMMY=same", current="DUMMY=same")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(uploaded)
        self.assertEqual(output, "")

    def test_missing_env_skips_upload(self):
        result, output, uploaded = self.run_upload("")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(uploaded)
        self.assertEqual(output, "")

    def test_failed_upload_cleans_up_without_changed_marker(self):
        result, output, uploaded = self.run_upload("DUMMY=failure", fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(uploaded)
        self.assertEqual(output, "")
