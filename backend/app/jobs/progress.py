import asyncio
from collections.abc import Awaitable, Callable

import psutil

ProgressSink = Callable[[int], Awaitable[None]]


async def run_resource_progress(
    sink: ProgressSink,
    budget_seconds: float,
    stopped: Callable[[], bool],
    interval: float = 0.5,
) -> None:
    """Avanza el progreso según el consumo de CPU mientras una generación corre."""
    active = 0.0
    elapsed = 0.0
    psutil.cpu_percent(interval=None)
    while not stopped():
        await asyncio.sleep(interval)
        cpu = psutil.cpu_percent(interval=None)
        elapsed += interval
        if cpu >= 15:
            active += interval
        ratio = (0.6 * active + 0.4 * elapsed) / budget_seconds
        await sink(min(90, int(ratio * 100)))