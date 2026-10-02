import asyncio
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.models import AssetKind, Episode, ResourceVariant
from app.providers import get_provider
from app.services.srt import SrtEntry, build_srt
from app.services.storage import asset_dir

DEFAULT_VOICE = "es-ES-AlvaroNeural"


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


async def _mix_fragment(video_path: Path, line_audios: list[Path], offsets: list[float], out: Path) -> None:
    n = len(line_audios)
    if n == 0:
        await _run_ffmpeg(["-i", str(video_path), "-c", "copy", str(out)])
        return
    inputs: list[str] = ["-i", str(video_path)]
    for audio in line_audios:
        inputs += ["-i", str(audio)]
    parts = []
    for i, offset in enumerate(offsets, start=1):
        ms = int(round(offset * 1000))
        parts.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
    mix_in = "".join(f"[a{i}]" for i in range(1, n + 1))
    parts.append(f"{mix_in}amix=inputs={n}:duration=longest:normalize=0[aout]")
    await _run_ffmpeg(
        [
            *inputs,
            "-filter_complex",
            ";".join(parts),
            "-map",
            "0:v",
            "-map",
            "[aout]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(out),
        ]
    )


def _escape_filter_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace(":", "\\:")


async def assemble_episode(session, episode_id: int, subtitle_burn: bool) -> dict:
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
    audio_dir = asset_dir(project_id, AssetKind.audio)
    audio_dir.mkdir(parents=True, exist_ok=True)
    work_dir = Path(settings.storage_dir) / str(project_id) / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    out_dir = asset_dir(project_id, AssetKind.episode) / str(episode_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    tts_provider = get_provider("tts", None)

    srt_entries: list[SrtEntry] = []
    processed: list[Path] = []
    time_cursor = 0.0

    for idx, fragment in enumerate(fragments):
        video_path = storage / fragment.video_path
        duration = await _ffprobe_duration(video_path)
        line_audios: list[Path] = []
        offsets: list[float] = []
        line_offset = 0.5
        for line in sorted(fragment.dialogue_lines, key=lambda l: l.order):
            voice_name = DEFAULT_VOICE
            if line.character_variant_id:
                variant = await session.get(ResourceVariant, line.character_variant_id)
                if variant and variant.voice and variant.voice.get("voice"):
                    voice_name = variant.voice["voice"]
            tts = await tts_provider.synthesize(line.text, voice_name)
            line_audios.append(tts.path)
            offsets.append(line_offset)
            srt_entries.append(
                SrtEntry(
                    start_seconds=time_cursor + line_offset,
                    end_seconds=time_cursor + line_offset + tts.duration_seconds,
                    text=line.text,
                )
            )
            line_offset += tts.duration_seconds + 0.3

        processed_path = work_dir / f"{idx:03d}_{fragment.id}.mp4"
        await _mix_fragment(video_path, line_audios, offsets, processed_path)
        processed.append(processed_path)
        time_cursor += duration

    concat_list = work_dir / "concat.txt"
    concat_list.write_text(
        "\n".join(f"file '{p.resolve().as_posix()}'" for p in processed),
        encoding="utf-8",
    )
    final_path = out_dir / "final.mp4"
    await _run_ffmpeg(
        ["-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(final_path)]
    )

    srt_path = out_dir / "final.srt"
    srt_path.write_text(build_srt(srt_entries), encoding="utf-8")

    final_rel = final_path.relative_to(storage).as_posix()
    srt_rel = srt_path.relative_to(storage).as_posix()
    result_dict = {"final": final_rel, "srt": srt_rel, "fragments": len(fragments)}

    if subtitle_burn:
        burned = out_dir / "final_burn.mp4"
        await _run_ffmpeg(
            [
                "-i",
                str(final_path),
                "-vf",
                f"subtitles='{_escape_filter_path(srt_path)}'",
                "-c:a",
                "copy",
                str(burned),
            ]
        )
        result_dict["final_burn"] = burned.relative_to(storage).as_posix()

    for p in processed:
        p.unlink(missing_ok=True)
    concat_list.unlink(missing_ok=True)

    episode.status = "assembled"
    return result_dict
