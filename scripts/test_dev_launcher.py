"""Launcher tests for ./run.sh.

These tests stub uv, bun, docker, and ss. They check exit codes and child
processes. They do not start real servers, Docker, or network services.
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
LAUNCHER = REPO / "run.sh"

# A remote URL planted in the environment. The launcher must not print it.
REMOTE_DATABASE_URL = "postgresql+psycopg://app_user:super-secret-db-password@db.internal.example:5432/rounds"
REMOTE_SECRET = "super-secret-db-password"
AWS_SECRET = "aws-secret-access-key-value"
# Same host, port, and database as docker-compose.yml, with the app's psycopg driver.
LOCAL_DATABASE_URL = "postgresql+psycopg://rounds:rounds@127.0.0.1:5433/rounds"


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.stub_dir = self.root / "bin"
        self.stub_dir.mkdir()
        self.log_path = self.root / "stub-log.jsonl"
        self.pid_dir = self.root / "pids"
        self.pid_dir.mkdir()
        self.addCleanup(self._stop_recorded_processes)
        self._write_stub()
        # Remember a real .env so a test can restore it if the script touches the file.
        self.env_file = REPO / ".env"
        self.env_existed = self.env_file.exists()
        self.env_bytes = self.env_file.read_bytes() if self.env_existed else None

    def tearDown(self):
        if self.env_existed:
            self.env_file.write_bytes(self.env_bytes)
        elif self.env_file.exists():
            self.env_file.unlink()

    def test_generation_failure_launches_neither_server(self):
        result = self.run_launcher({"STUB_BUN_GENERATE_FAIL": "1"})

        self.assertNotEqual(result.returncode, 0)
        commands = [item["args"] for item in self.invocations()]
        self.assertTrue(any("api:generate" in args for args in commands))
        self.assertFalse(any("uvicorn" in args for args in commands))
        self.assertFalse(any(args == "run dev" or args.startswith("run dev ") for args in commands))
        self.assertNotIn(REMOTE_SECRET, result.stdout + result.stderr)
        self.assertNotIn(AWS_SECRET, result.stdout + result.stderr)

    def test_contract_check_failure_launches_neither_server(self):
        result = self.run_launcher({"STUB_BUN_CHECK_FAIL": "1"})

        self.assertNotEqual(result.returncode, 0)
        commands = [item["args"] for item in self.invocations()]
        self.assertTrue(any("api:generate" in args for args in commands))
        self.assertTrue(any("api:check" in args for args in commands))
        self.assertFalse(any("uvicorn" in args for args in commands))
        self.assertFalse(self._dev_server_started(commands))

    def test_backend_install_failure_launches_neither_server(self):
        result = self.run_launcher({"STUB_UV_SYNC_FAIL": "1"})

        self.assertNotEqual(result.returncode, 0)
        commands = [item["args"] for item in self.invocations()]
        self.assertTrue(any(args.startswith("sync ") or args == "sync" for args in commands))
        self.assertTrue(any("--frozen" in args and "sync" in args for args in commands))
        self.assertFalse(any("uvicorn" in args for args in commands))
        self.assertFalse(self._dev_server_started(commands))
        self.assertFalse(any("api:generate" in args for args in commands))

    def test_frontend_install_failure_launches_neither_server(self):
        result = self.run_launcher({"STUB_BUN_INSTALL_FAIL": "1"})

        self.assertNotEqual(result.returncode, 0)
        rows = self.invocations()
        commands = [item["args"] for item in rows]
        install = [item for item in rows if item["cmd"] == "bun" and "install" in item["args"]]
        self.assertEqual(len(install), 1)
        self.assertIn("--frozen-lockfile", install[0]["args"])
        self.assertTrue(install[0]["cwd"].endswith("/frontend"))
        self.assertFalse(any("api:generate" in args for args in commands))
        self.assertFalse(any("uvicorn" in args for args in commands))
        self.assertFalse(self._dev_server_started(commands))

    def test_ordinary_startup_uses_configured_database_without_migrate_or_seed(self):
        before = self._snapshot_env_file()
        result = self.run_launcher(stop_signal=signal.SIGTERM)

        self.assertIn(result.returncode, (128 + signal.SIGTERM, -signal.SIGTERM))
        self._assert_env_file_unchanged(before)
        steps = self._steps()
        names = [name for name, _item in steps]
        # The two servers are started independently, so either may be logged first.
        self.assertEqual(names[:4], ["sync", "install", "generate", "check"])
        self.assertEqual(sorted(names[4:]), ["api", "web"])
        by_name = {name: item for name, item in steps}
        sync = by_name["sync"]
        install = by_name["install"]
        generate = by_name["generate"]
        api = by_name["api"]
        web = by_name["web"]
        self.assertIn("--frozen", sync["args"])
        self.assertTrue(sync["cwd"].endswith("/backend"))
        self.assertIn("--frozen-lockfile", install["args"])
        self.assertTrue(install["cwd"].endswith("/frontend"))
        self.assertEqual(generate["cwd"], str(REPO))
        self.assertIn("--reload", api["args"])
        self.assertIn("--port 8000", api["args"])
        self.assertTrue(api["cwd"].endswith("/backend"))
        self.assertEqual(api["database_url"], REMOTE_DATABASE_URL)
        self.assertIn("--port 5173", web["args"])
        self.assertIn("--strictPort", web["args"])
        self.assertTrue(web["cwd"].endswith("/frontend"))
        self.assertEqual(web["database_url"], REMOTE_DATABASE_URL)
        self.assertNotIn("alembic", " ".join(item["args"] for item in self.invocations()))
        self.assertNotIn("seed_golden", " ".join(item["args"] for item in self.invocations()))
        self.assertFalse(any(item["cmd"] == "docker" for item in self.invocations()))
        self._assert_trees_reaped()
        output = result.stdout + result.stderr
        self.assertNotIn(REMOTE_SECRET, output)
        self.assertNotIn(AWS_SECRET, output)
        # The dev proxy and the API port have to stay the same, including for the deployed app's same-origin client.
        vite = (REPO / "frontend" / "vite.config.ts").read_text(encoding="utf-8")
        self.assertIn('"/api": "http://localhost:8000"', vite)
        self.assertIn("port: 5173", vite)

    def test_local_db_prepares_only_a_local_database(self):
        before = self._snapshot_env_file()
        result = self.run_launcher(args=["--local-db"], stop_signal=signal.SIGTERM)

        self.assertIn(result.returncode, (128 + signal.SIGTERM, -signal.SIGTERM))
        self._assert_env_file_unchanged(before)
        self._assert_trees_reaped()
        output = result.stdout + result.stderr
        self.assertNotIn(REMOTE_SECRET, output)
        self.assertNotIn("db.internal.example", output)
        self.assertNotIn(AWS_SECRET, output)

        rows = self.invocations()
        docker = [item for item in rows if item["cmd"] == "docker"]
        self.assertTrue(any(item["args"].startswith("compose up ") and item["cwd"] == str(REPO) for item in docker))
        self.assertTrue(any("pg_isready" in item["args"] and item["cwd"] == str(REPO) for item in docker))
        self.assertFalse(any("down" in item["args"].split() for item in docker))

        migrate = [item for item in rows if "alembic" in item["args"]]
        seed = [item for item in rows if "seed_golden_cases" in item["args"]]
        self.assertEqual(len(migrate), 1)
        self.assertIn("upgrade head", migrate[0]["args"])
        self.assertTrue(migrate[0]["cwd"].endswith("/backend"))
        self.assertEqual(len(seed), 1)
        self.assertIn("python -m scripts.seed_golden_cases", seed[0]["args"])
        self.assertTrue(seed[0]["cwd"].endswith("/backend"))

        servers = [item for item in rows if "uvicorn" in item["args"] or item["args"].startswith("run dev")]
        self.assertEqual(len(servers), 2)
        for item in migrate + seed + servers:
            self.assertEqual(item["database_url"], LOCAL_DATABASE_URL)
            self.assertNotIn("db.internal.example", item["args"])
            self.assertNotIn(REMOTE_SECRET, item["args"])

        # Readiness and seeding happen before either server is launched.
        kinds = []
        for item in rows:
            if item["cmd"] == "docker" and "pg_isready" in item["args"]:
                kinds.append("ready")
            elif "alembic" in item["args"]:
                kinds.append("migrate")
            elif "seed_golden_cases" in item["args"]:
                kinds.append("seed")
            elif "uvicorn" in item["args"] or item["args"].startswith("run dev"):
                kinds.append("server")
        self.assertEqual(kinds[:3], ["ready", "migrate", "seed"])
        self.assertTrue(kinds[3:])
        self.assertTrue(all(kind == "server" for kind in kinds[3:]))

    def test_local_db_docker_failure_launches_neither_server(self):
        result = self.run_launcher(
            {"STUB_DOCKER_UP_FAIL": "1"},
            args=["--local-db"],
            stop_signal=signal.SIGTERM,
        )

        self.assertNotEqual(result.returncode, 0)
        commands = [item["args"] for item in self.invocations()]
        self.assertFalse(any("alembic" in args for args in commands))
        self.assertFalse(any("seed_golden_cases" in args for args in commands))
        self.assertFalse(any("uvicorn" in args for args in commands))
        self.assertFalse(self._dev_server_started(commands))
        self.assertNotIn(REMOTE_SECRET, result.stdout + result.stderr)

    def test_busy_api_port_is_actionable_and_hides_secrets(self):
        result = self.run_launcher({"STUB_BUSY_PORT": "8000"}, stop_signal=signal.SIGTERM)

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(result.returncode, (128 + signal.SIGTERM, -signal.SIGTERM))
        output = result.stdout + result.stderr
        self.assertIn("8000", output)
        self.assertIn("Stop the other process", output)
        self.assertNotIn(REMOTE_SECRET, output)
        self.assertNotIn(AWS_SECRET, output)
        self.assertNotIn("db.internal.example", output)
        commands = [item["args"] for item in self.invocations()]
        self.assertFalse(any("uvicorn" in args for args in commands))
        self.assertFalse(self._dev_server_started(commands))

    def test_busy_frontend_port_is_actionable_and_hides_secrets(self):
        result = self.run_launcher({"STUB_BUSY_PORT": "5173"}, stop_signal=signal.SIGTERM)

        self.assertNotEqual(result.returncode, 0)
        output = result.stdout + result.stderr
        self.assertIn("5173", output)
        self.assertIn("Stop the other process", output)
        self.assertNotIn(REMOTE_SECRET, output)
        commands = [item["args"] for item in self.invocations()]
        self.assertFalse(any("uvicorn" in args for args in commands))
        self.assertFalse(self._dev_server_started(commands))

    def test_missing_uv_is_actionable_and_hides_secrets(self):
        (self.stub_dir / "uv").unlink()
        result = self.run_launcher(stop_signal=signal.SIGTERM)

        self.assertNotEqual(result.returncode, 0)
        output = result.stdout + result.stderr
        self.assertIn("uv", output)
        self.assertIn("Install", output)
        self.assertNotIn(REMOTE_SECRET, output)
        self.assertNotIn(AWS_SECRET, output)
        self.assertFalse(any("uvicorn" in item["args"] for item in self.invocations()))

    def test_missing_bun_is_actionable_and_hides_secrets(self):
        (self.stub_dir / "bun").unlink()
        result = self.run_launcher(stop_signal=signal.SIGTERM)

        self.assertNotEqual(result.returncode, 0)
        output = result.stdout + result.stderr
        self.assertIn("bun", output)
        self.assertIn("Install", output)
        self.assertNotIn(REMOTE_SECRET, output)
        self.assertFalse(self._dev_server_started([item["args"] for item in self.invocations()]))

    def test_missing_docker_on_local_db_is_actionable_and_hides_secrets(self):
        (self.stub_dir / "docker").unlink()
        result = self.run_launcher(args=["--local-db"], stop_signal=signal.SIGTERM)

        self.assertNotEqual(result.returncode, 0)
        output = result.stdout + result.stderr
        self.assertIn("Docker", output)
        self.assertIn("Install", output)
        self.assertNotIn(REMOTE_SECRET, output)
        commands = [item["args"] for item in self.invocations()]
        self.assertFalse(any("uvicorn" in args for args in commands))
        self.assertFalse(any("alembic" in args for args in commands))

    def test_missing_port_tool_is_actionable_and_hides_secrets(self):
        (self.stub_dir / "ss").unlink()
        result = self.run_launcher(stop_signal=signal.SIGTERM)

        self.assertNotEqual(result.returncode, 0)
        output = result.stdout + result.stderr
        self.assertIn("lsof", output)
        self.assertNotIn(REMOTE_SECRET, output)
        self.assertFalse(any("uvicorn" in item["args"] for item in self.invocations()))

    def test_ctrl_c_stops_owned_trees_and_spares_unrelated_processes(self):
        unrelated = subprocess.Popen(["sleep", "60"], start_new_session=True)
        self.addCleanup(self._kill_if_running, unrelated)
        result = self.run_launcher(stop_signal=signal.SIGINT)

        self.assertIn(result.returncode, (128 + signal.SIGINT, -signal.SIGINT))
        self._assert_trees_reaped()
        self.assertIsNone(unrelated.poll())
        self.assertFalse(any(item["cmd"] == "docker" and "down" in item["args"] for item in self.invocations()))

    def test_api_exit_stops_the_frontend_and_keeps_its_status(self):
        result = self.run_launcher({"STUB_API_EXIT": "4"})

        self.assertEqual(result.returncode, 4)
        self._assert_trees_reaped()

    def test_frontend_exit_stops_the_api_and_keeps_its_status(self):
        result = self.run_launcher({"STUB_WEB_EXIT": "5"})

        self.assertEqual(result.returncode, 5)
        self._assert_trees_reaped()

    def _kill_if_running(self, proc):
        if proc.poll() is None:
            os.kill(proc.pid, signal.SIGKILL)
            proc.wait(timeout=2)

    def _dev_server_started(self, commands):
        return any(args == "run dev" or args.startswith("run dev ") for args in commands)

    def _steps(self):
        """Startup commands in the order the stubs observed them."""
        steps = []
        for item in self.invocations():
            args = item["args"]
            if item["cmd"] == "uv" and "sync" in args.split():
                steps.append(("sync", item))
            elif item["cmd"] == "bun" and args.startswith("install"):
                steps.append(("install", item))
            elif "api:generate" in args:
                steps.append(("generate", item))
            elif "api:check" in args:
                steps.append(("check", item))
            elif "uvicorn" in args:
                steps.append(("api", item))
            elif item["cmd"] == "bun" and (args == "run dev" or args.startswith("run dev ")):
                steps.append(("web", item))
        return steps

    def _snapshot_env_file(self):
        # None means the shared environment file was absent. Creating one would change the worktree.
        if not self.env_file.exists():
            return None
        return self.env_file.read_bytes()

    def _assert_env_file_unchanged(self, before):
        if before is None:
            self.assertFalse(self.env_file.exists())
            return
        self.assertEqual(self.env_file.read_bytes(), before)

    def _read_pid(self, name):
        path = self.pid_dir / name
        if not path.exists():
            return None
        return int(path.read_text(encoding="utf-8").strip())

    def _alive(self, pid):
        if pid is None:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        return True

    def _servers_ready(self):
        return all(self._read_pid(name) is not None for name in ("api.pid", "api.child", "web.pid", "web.child"))

    def _assert_trees_reaped(self):
        for name in ("api.pid", "api.child", "web.pid", "web.child"):
            self.assertFalse(self._alive(self._read_pid(name)), name)

    def _stop_recorded_processes(self):
        for name in ("api.pid", "api.child", "web.pid", "web.child"):
            pid = self._read_pid(name)
            if pid is None:
                continue
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

    def run_launcher(self, extra_env=None, args=None, timeout=8, stop_signal=None):
        """Run ./run.sh from a directory that is not the repository."""
        env = os.environ.copy()
        # Only the stubs and ps are visible, so a test cannot start real uv, bun, or Docker.
        env["PATH"] = f"{self.stub_dir}{os.pathsep}{self._system_bin()}"
        env["STUB_LOG"] = str(self.log_path)
        env["STUB_PID_DIR"] = str(self.pid_dir)
        env["DATABASE_URL"] = REMOTE_DATABASE_URL
        env["AWS_SECRET_ACCESS_KEY"] = AWS_SECRET
        env.pop("STUB_BUN_GENERATE_FAIL", None)
        env.pop("STUB_BUN_CHECK_FAIL", None)
        env.pop("STUB_BUN_INSTALL_FAIL", None)
        env.pop("STUB_UV_SYNC_FAIL", None)
        env.pop("STUB_DOCKER_UP_FAIL", None)
        env.pop("STUB_API_EXIT", None)
        env.pop("STUB_WEB_EXIT", None)
        env.pop("STUB_BUSY_PORT", None)
        if extra_env:
            env.update(extra_env)

        work = self.root / "elsewhere"
        work.mkdir(exist_ok=True)
        proc = subprocess.Popen(
            [shutil.which("bash"), str(LAUNCHER), *(args or [])],
            cwd=work,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        deadline = time.monotonic() + timeout
        try:
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    break
                # Stop only after both server trees exist, so cleanup has something to reap.
                if stop_signal is not None and self._servers_ready():
                    os.kill(proc.pid, stop_signal)
                    break
                time.sleep(0.05)
            else:
                raise subprocess.TimeoutExpired(proc.args, timeout)
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired as exc:
            self._stop_recorded_processes()
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
            proc.wait(timeout=2)
            self.fail(f"run.sh did not exit within {timeout}s\nstdout={exc.stdout}\nstderr={exc.stderr}")
        return subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)

    def invocations(self):
        if not self.log_path.exists():
            return []
        rows = []
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def _write_stub(self):
        """One stub binary, copied to the command names ./run.sh is expected to call."""
        script = textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            import os
            import pathlib
            import signal
            import sys
            import time

            name = pathlib.Path(sys.argv[0]).name
            args = sys.argv[1:]
            record = {
                "cmd": name,
                "args": " ".join(args),
                "cwd": os.getcwd(),
                "database_url": os.environ.get("DATABASE_URL", ""),
            }
            with open(os.environ["STUB_LOG"], "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record) + "\\n")

            def flagged(key):
                return os.environ.get(key) == "1"

            if name == "uv" and "sync" in args and flagged("STUB_UV_SYNC_FAIL"):
                sys.exit(1)
            if name == "bun" and "install" in args and flagged("STUB_BUN_INSTALL_FAIL"):
                sys.exit(1)
            if name == "bun" and "api:generate" in args and flagged("STUB_BUN_GENERATE_FAIL"):
                sys.exit(1)
            if name == "bun" and "api:check" in args and flagged("STUB_BUN_CHECK_FAIL"):
                sys.exit(1)
            if name == "docker" and "up" in args and flagged("STUB_DOCKER_UP_FAIL"):
                sys.exit(1)
            if name == "ss":
                port = os.environ.get("STUB_BUSY_PORT", "")
                if port:
                    sys.stdout.write(f"LISTEN 0 128 127.0.0.1:{port} 0.0.0.0:*\\n")
                sys.exit(0)

            is_api = name == "uv" and "uvicorn" in args
            is_web = name == "bun" and "dev" in args
            if not is_api and not is_web:
                sys.exit(0)

            role = "api" if is_api else "web"
            pid_dir = pathlib.Path(os.environ["STUB_PID_DIR"])
            (pid_dir / f"{role}.pid").write_text(str(os.getpid()), encoding="utf-8")
            child = os.fork()
            if child == 0:
                time.sleep(60)
                os._exit(0)
            (pid_dir / f"{role}.child").write_text(str(child), encoding="utf-8")

            exit_now = os.environ.get("STUB_API_EXIT" if is_api else "STUB_WEB_EXIT", "")
            if exit_now != "":
                os._exit(int(exit_now))

            def stop(_signum, _frame):
                try:
                    os.kill(child, signal.SIGTERM)
                    os.waitpid(child, 0)
                except OSError:
                    pass
                os._exit(0)

            signal.signal(signal.SIGTERM, stop)
            signal.signal(signal.SIGINT, stop)
            while True:
                time.sleep(60)
            """
        )
        # Absolute interpreter so the stub runs when the launcher's PATH is locked down.
        script = script.replace("#!/usr/bin/env python3", f"#!{sys.executable}", 1)
        for command in ("uv", "bun", "docker", "ss"):
            path = self.stub_dir / command
            path.write_text(script, encoding="utf-8")
            path.chmod(0o755)

    def _system_bin(self):
        """Directory that contains ps and nothing else the launcher might call."""
        folder = self.root / "system-bin"
        folder.mkdir(exist_ok=True)
        ps = shutil.which("ps")
        if ps is None:
            raise AssertionError("ps is required to observe child processes")
        link = folder / "ps"
        if not link.exists():
            link.symlink_to(ps)
        return str(folder)


if __name__ == "__main__":
    unittest.main()
