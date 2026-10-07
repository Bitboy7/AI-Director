import asyncio
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.models import AssetKind, Episode, Project
from app.services.storage import asset_dir


class AssemblyMissingFragmentsError(Exception):
    pass


async def _ffprobe_duration(path: Path) -> float:
    proc = await asyncio.create_subprocess_exec(
        get_settings().ffprobe_path,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "csv=p=0",
        str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe falló para {path}: {stderr.decode()}")
    return float(stdout.decode().strip())


async def _run_ffmpeg(args: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(
        get_settings().ffmpeg_path,
        "-y",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg falló: {stderr.decode(errors='replace')[-500:]}")


async def _has_audio(path: Path) -> bool:
    proc = await asyncio.create_subprocess_exec(
        get_settings().ffprobe_path,
        "-v",
        "error",
        "-select_streams",
        "a",
        "-show_entries",
        "stream=index",
        "-of",
        "csv=p=0",
        str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return bool(stdout.decode().strip())


def _target_size(aspect_ratio: str) -> tuple[int, int]:
    if aspect_ratio == "9:16":
        return 720, 1280
    if aspect_ratio == "1:1":
        return 1080, 1080
    return 1280, 720


async def assemble_episode(
    session, episode_id: int, subtitle_burn: bool = False, on_progress=None
) -> dict:
    """Une los fragmentos del episodio en un único video conservando su audio.

    No sintetiza voz ni genera subtítulos: el audio de cada fragmento es el
    generado por el proveedor de video (se conserva tal cual).
    """
    settings = get_settings()
    result = await session.execute(select(Episode).where(Episode.id == episode_id))
    episode = result.scalar_one()
    fragments = sorted(episode.fragments, key=lambda f: f.shot_number)

    missing = [f"{episode.number}-{f.shot_number}" for f in fragments if not f.video_path]
    if missing:
        raise AssemblyMissingFragmentsError(
            "faltan videos para los planos: " + ", ".join(f"[{m}]" for m in missing)
        )

    storage = settings.storage_dir.resolve()
    project_id = episode.project_id
    project = await session.get(Project, project_id)
    aspect = (project.aspect_ratio if project else None) or "16:9"
    width, height = _target_size(aspect)

    out_dir = asset_dir(project_id, AssetKind.episode) / str(episode_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    inputs: list[str] = []
    filters: list[str] = []
    concat_labels: list[str] = []
    input_count = 0
    total_duration = 0.0

    for idx, fragment in enumerate(fragments):
        video_path = storage / fragment.video_path
        duration = await _ffprobe_duration(video_path)
        total_duration += duration
        inputs += ["-i", str(video_path)]
        video_index = input_count
        input_count += 1

        filters.append(
            f"[{video_index}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24[v{idx}]"
        )

        if await _has_audio(video_path):
            audio_src = f"[{video_index}:a]"
        else:
            inputs += [
                "-t",
                f"{duration}",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=48000:cl=stereo",
            ]
            audio_src = f"[{input_count}:a]"
            input_count += 1
        filters.append(
            f"{audio_src}aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a{idx}]"
        )
        concat_labels.append(f"[v{idx}][a{idx}]")

        if on_progress is not None:
            await on_progress(min(99, int((idx + 1) / len(fragments) * 100)))

    filters.append(
        "".join(concat_labels) + f"concat=n={len(fragments)}:v=1:a=1[vout][aout]"
    )

    final_path = out_dir / "final.mp4"
    await _run_ffmpeg(
        [
            *inputs,
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            "-t",
            f"{total_duration:.3f}",
            str(final_path),
        ]
    )

    final_rel = final_path.relative_to(storage).as_posix()
    episode.status = "assembled"
    return {"final": final_rel, "fragments": len(fragments)}
