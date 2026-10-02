import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import start  # noqa: E402


def test_parse_redis_location_default():
    assert start.parse_redis_location("redis://localhost:6379") == ("localhost", 6379)


def test_parse_redis_location_custom_port():
    assert start.parse_redis_location("redis://127.0.0.1:6380") == ("127.0.0.1", 6380)


def test_build_service_commands_default():
    commands = start.build_service_commands("py", no_frontend=False, npm="npm")
    names = [c["name"] for c in commands]
    assert names == ["api", "worker-default", "worker-video", "worker-assembly", "frontend"]


def test_build_service_commands_no_frontend():
    commands = start.build_service_commands("py", no_frontend=True)
    names = [c["name"] for c in commands]
    assert "frontend" not in names
    assert commands[0]["cmd"][:3] == ["py", "-m", "uvicorn"]


def test_build_service_commands_workers():
    commands = start.build_service_commands("py", no_frontend=True)
    workers = [c for c in commands if c["name"].startswith("worker-")]
    assert len(workers) == 3
    assert workers[0]["cmd"][-1] == "default"
    assert workers[1]["cmd"][-1] == "video"
    assert workers[2]["cmd"][-1] == "assembly"


def test_npm_cmd_uses_which(monkeypatch):
    monkeypatch.setattr(
        start.shutil, "which", lambda name: "C:/node/npm.cmd" if name == "npm" else None
    )
    assert start.npm_cmd() == "C:/node/npm.cmd"


def test_build_service_commands_frontend_uses_npm():
    commands = start.build_service_commands("py", no_frontend=False, npm="npm.cmd")
    frontend = [c for c in commands if c["name"] == "frontend"][0]
    assert frontend["cmd"][0] == "npm.cmd"


def test_build_service_commands_skips_frontend_without_npm():
    commands = start.build_service_commands("py", no_frontend=False, npm=None)
    assert "frontend" not in [c["name"] for c in commands]


def test_service_log_path():
    path = start.service_log_path("api")
    assert path.name == "api.log"
    assert path.parent == Path(start.__file__).resolve().parent / "logs"


def test_build_parser_flags():
    parser = start.build_parser()
    args = parser.parse_args(["--no-frontend", "--skip-install"])
    assert args.no_frontend is True
    assert args.skip_install is True
    assert args.check is False


def test_ensure_redis_docker_timeout_returns_false(monkeypatch):
    import subprocess as sp

    def fake_docker(cmd, **kwargs):
        raise sp.TimeoutExpired(cmd, 10)

    monkeypatch.setattr(
        start.shutil, "which", lambda name: "docker" if name == "docker" else None
    )
    monkeypatch.setattr(start.subprocess, "run", fake_docker)
    monkeypatch.setattr(start, "is_port_open", lambda host, port, timeout=0.5: False)

    assert start.ensure_redis("redis://localhost:6379") is False
