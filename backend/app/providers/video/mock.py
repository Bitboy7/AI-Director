import asyncio
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from app.config import get_settings
from app.providers.base import VideoProvider, VideoSubmitPayload, VideoTaskStatus


class MockVideoProvider(VideoProvider):
    def __init__(self) -> None:
        self._tasks: dict[str, dict] = {}
        self._tmp = Path(tempfile.mkdtemp(prefix="mock-video-"))

    def _resolution(self, aspect_ratio: str) -> tuple[int, int]:
        if aspect_ratio == "9:16":
            return (720, 1280)
        return (1280, 720)

    async def submit(self, payload: VideoSubmitPayload) -> str:
        task_id = uuid4().hex
        out = self._tmp / f"{task_id}.mp4"
        self._tasks[task_id] = {"state": "queued", "path": out, "error": None}
        asyncio.create_task(self._generate(task_id, payload, out))
        return task_id

    async def _generate(
        self, task_id: str, payload: VideoSubmitPayload, out: Path
    ) -> None:
        self._tasks[task_id]["state"] = "processing"
        w, h = self._resolution(payload.aspect_ratio)
        cmd = [
            get_settings().ffmpeg_path,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x3355aa:s={w}x{h}:r=24",
            "-t",
            str(payload.duration_seconds),
            "-pix_fmt",
            "yuv420p",
            str(out),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode == 0:
            self._tasks[task_id]["state"] = "succeeded"
        else:
            self._tasks[task_id]["state"] = "failed"
            self._tasks[task_id]["error"] = stderr.decode(errors="replace")[-500:]

    async def poll(self, task_id: str) -> VideoTaskStatus:
        task = self._tasks.get(task_id)
        if task is None:
            return VideoTaskStatus(state="failed", error="unknown task")
        if task["state"] == "succeeded":
            return VideoTaskStatus(state="succeeded", video_url=str(task["path"]))
        if task["state"] == "failed":
            return VideoTaskStatus(state="failed", error=task["error"])
        return VideoTaskStatus(state=task["state"])

    async def download(self, url: str, dest: Path) -> Path:
        src = Path(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        return dest
