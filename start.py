#!/usr/bin/env python3
"""Arranca todos los servicios de AI Director con un solo comando.

Uso:
    python start.py                  # API + workers + frontend (+ Redis via Docker si falta)
    python start.py --no-frontend    # solo backend (API + workers)
    python start.py --skip-install   # no instala dependencias
    python start.py --check          # verifica el entorno sin arrancar nada

Los logs del script van a logs/start.log y los de cada servicio a
logs/<servicio>.log.
"""

import argparse
import logging
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
LOGS_DIR = ROOT / "logs"
REDIS_CONTAINER = "ai-director-redis"
DEFAULT_REDIS_URL = "redis://localhost:6379"

logger = logging.getLogger("start")


def service_log_path(name: str) -> Path:
    return LOGS_DIR / f"{name}.log"


def setup_logging() -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    logger.setLevel(logging.INFO)
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
    file_handler = logging.FileHandler(LOGS_DIR / "start.log", encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(console)
    logger.addHandler(file_handler)
    logger.propagate = False


def is_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def parse_redis_location(redis_url: str) -> tuple[str, int]:
    parsed = urlparse(redis_url)
    return (parsed.hostname or "localhost", parsed.port or 6379)


def venv_python() -> str:
    if os.name == "nt":
        return str(BACKEND / ".venv" / "Scripts" / "python.exe")
    return str(BACKEND / ".venv" / "bin" / "python")


def build_service_commands(python: str, no_frontend: bool) -> list[dict]:
    commands = [
        {
            "name": "api",
            "cmd": [python, "-m", "uvicorn", "app.main:app", "--port", "8000"],
            "cwd": BACKEND,
        }
    ]
    for queue in ("default", "video", "assembly"):
        commands.append(
            {
                "name": f"worker-{queue}",
                "cmd": [python, "-m", "app.jobs.run", queue],
                "cwd": BACKEND,
            }
        )
    if not no_frontend:
        commands.append({"name": "frontend", "cmd": ["npm", "run", "dev"], "cwd": FRONTEND})
    return commands


def ensure_backend_venv(skip_install: bool = False) -> str:
    python = venv_python()
    marker = Path(python).parent / ".deps-installed"
    needs_install = (
        not skip_install
        and (not marker.exists() or BACKEND / "pyproject.toml" > marker)
    )
    if not Path(python).exists():
        logger.info("Creando entorno virtual del backend...")
        subprocess.run([sys.executable, "-m", "venv", str(BACKEND / ".venv")], check=True)
        needs_install = not skip_install
    if needs_install:
        logger.info("Instalando dependencias del backend...")
        subprocess.run(
            [python, "-m", "pip", "install", "--quiet", "-e", ".[dev]"],
            cwd=BACKEND,
            check=True,
        )
        marker.touch()
    if not Path(BACKEND / ".env").exists() and (BACKEND / ".env.example").exists():
        shutil.copyfile(BACKEND / ".env.example", BACKEND / ".env")
        logger.info("Creado backend/.env desde .env.example")
    return python


def ensure_frontend_deps(skip_install: bool = False) -> None:
    if not (FRONTEND / "package.json").exists():
        return
    marker = FRONTEND / "node_modules" / ".package-lock.json"
    needs_install = (
        not skip_install
        and (not marker.exists() or FRONTEND / "package.json" > marker)
    )
    if not (FRONTEND / "node_modules").exists():
        needs_install = not skip_install
    if needs_install:
        logger.info("Instalando dependencias del frontend...")
        subprocess.run(["npm", "install", "--no-audit", "--no-fund"], cwd=FRONTEND, check=True)


def _docker_run(docker: str, args: list[str], timeout: int = 60) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [docker, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0, result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.warning("docker no respondio en %ss; se ignora", timeout)
        return False, ""


def ensure_redis(redis_url: str) -> bool:
    host, port = parse_redis_location(redis_url)
    if is_port_open(host, port):
        logger.info("Redis disponible en %s:%s", host, port)
        return True
    docker = shutil.which("docker")
    if docker is None:
        logger.warning("Redis no esta corriendo y no hay Docker en PATH")
        return False
    logger.info("Redis no esta corriendo; levantandolo con Docker...")
    ok, status = _docker_run(
        docker,
        ["ps", "-a", "--filter", f"name={REDIS_CONTAINER}", "--format", "{{.Status}}"],
        timeout=10,
    )
    if not ok:
        logger.warning("El demonio de Docker no responde; no se puede levantar Redis")
        return False
    if status:
        if not status.startswith("Up"):
            logger.info("Arrancando contenedor %s existente...", REDIS_CONTAINER)
            ok, _ = _docker_run(docker, ["start", REDIS_CONTAINER], timeout=60)
    else:
        logger.info("Creando contenedor %s (imagen redis:7-alpine)...", REDIS_CONTAINER)
        ok, _ = _docker_run(
            docker,
            ["run", "-d", "--name", REDIS_CONTAINER, "-p", "6379:6379", "redis:7-alpine"],
            timeout=120,
        )
    if not ok:
        logger.warning("Docker no pudo arrancar Redis; la cola de trabajos no funcionara")
        return False
    for _ in range(30):
        if is_port_open(host, port):
            logger.info("Redis listo en %s:%s", host, port)
            return True
        time.sleep(0.5)
    logger.warning("Redis no respondio tras 15s; la cola de trabajos no funcionara")
    return False


def check_environment(redis_url: str) -> int:
    problems: list[str] = []
    if shutil.which("ffmpeg") is None and not os.environ.get("FFMPEG_PATH"):
        problems.append("ffmpeg no esta en PATH (necesario para ensamblar videos)")
    host, port = parse_redis_location(redis_url)
    if is_port_open(host, port):
        logger.info("Redis disponible en %s:%s", host, port)
    elif shutil.which("docker"):
        logger.warning("Redis no esta corriendo (se levantara con Docker al arrancar)")
    else:
        problems.append("Redis no disponible y no hay Docker: la cola de trabajos no funcionara")
    if shutil.which("ollama"):
        logger.info("Ollama disponible")
    else:
        logger.warning("Ollama no esta en PATH (la generacion de guiones fallara)")
    if not problems:
        logger.info("Entorno listo")
        return 0
    for problem in problems:
        logger.error("%s", problem)
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Arranca todos los servicios de AI Director")
    parser.add_argument("--no-frontend", action="store_true", help="no arrancar Vite")
    parser.add_argument("--skip-install", action="store_true", help="no instalar dependencias")
    parser.add_argument("--check", action="store_true", help="solo verificar el entorno")
    parser.add_argument(
        "--redis-url",
        default=os.environ.get("REDIS_URL", DEFAULT_REDIS_URL),
        help="URL de Redis (default: redis://localhost:6379)",
    )
    return parser


def run_services(commands: list[dict], no_frontend: bool) -> int:
    processes: list[tuple[dict, subprocess.Popen]] = []
    logger.info("Arrancando %d servicios (Ctrl+C para detener todo)", len(commands))
    for spec in commands:
        log_path = service_log_path(spec["name"])
        log_handle = log_path.open("w", encoding="utf-8", buffering=1)
        logger.info("%s: %s -> %s", spec["name"], " ".join(spec["cmd"]), log_path)
        proc = subprocess.Popen(
            spec["cmd"],
            cwd=spec["cwd"],
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
        processes.append((spec, proc))

    logger.info("API      http://localhost:8000/docs")
    if not no_frontend:
        logger.info("Frontend http://localhost:5173")

    try:
        while True:
            for spec, proc in list(processes):
                code = proc.poll()
                if code is not None:
                    logger.error(
                        "%s termino inesperadamente (codigo %s) - ver %s",
                        spec["name"],
                        code,
                        service_log_path(spec["name"]),
                    )
                    processes.remove((spec, proc))
            if not processes:
                logger.error("Todos los servicios terminaron; saliendo")
                return 1
            time.sleep(2)
    except KeyboardInterrupt:
        logger.info("Deteniendo servicios...")
        for _, proc in processes:
            proc.terminate()
        for _, proc in processes:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        logger.info("Listo.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging()
    logger.info("AI Director - iniciando (args: %s)", vars(args))

    if args.check:
        return check_environment(args.redis_url)

    python = ensure_backend_venv(skip_install=args.skip_install)
    ensure_frontend_deps(skip_install=args.skip_install)
    ensure_redis(args.redis_url)

    commands = build_service_commands(python, no_frontend=args.no_frontend)
    return run_services(commands, no_frontend=args.no_frontend)


if __name__ == "__main__":
    sys.exit(main())
