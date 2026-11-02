import os
import runpy
import socket
import subprocess
import sys
import time

import httpx
import pytest


@pytest.mark.parametrize("entry", ["uvicorn", "module"])
def test_uvicorn_smoke(tmp_path, entry):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with (tmp_path / "uvicorn.log").open("w+") as log:
        command = (
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ]
            if entry == "uvicorn"
            else [sys.executable, "-m", "app"]
        )
        process = subprocess.Popen(
            command,
            env={
                **os.environ,
                "APP_ENV": "dev",
                "DATABASE_URL": f"sqlite:///{tmp_path / 'smoke.db'}",
                "EXPIRE_JOB_INTERVAL_S": "0",
                "SERVER_HOST": "127.0.0.1",
                "SERVER_PORT": str(port),
                "SERVER_RELOAD": "false",
            },
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 15
            with httpx.Client(timeout=0.5) as client:
                while time.monotonic() < deadline:
                    try:
                        response = client.get(f"http://127.0.0.1:{port}/health")
                        if response.status_code == 200:
                            assert response.json() == {"status": "ok", "db": True}
                            assert response.headers["X-Request-ID"]
                            return
                    except httpx.TransportError:
                        time.sleep(0.1)
                    if process.poll() is not None:
                        break
            log.seek(0)
            raise AssertionError(log.read())
        finally:
            process.terminate()
            process.wait(timeout=10)


def test_module_entry(monkeypatch, settings):
    from unittest.mock import Mock

    import uvicorn

    import app.core.config as config

    monkeypatch.setattr(config, "load_settings", lambda: settings)
    run = Mock()
    monkeypatch.setattr(uvicorn, "run", run)
    runpy.run_module("app.__main__", run_name="__main__")
    run.assert_called_once_with(
        "app.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.server_reload,
        log_level=settings.log_level,
    )
