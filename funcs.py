from pathlib import Path
from typing import Iterator, List

from ffmpeg_normalize import FFmpegNormalize


def normalize_audio(input_file: Path, output_file: Path) -> None:
    """音量を正規化"""

    print(f"音量正規化を開始: {input_file.name}")

    normalizer = FFmpegNormalize(
        normalization_type="ebu",
        target_level=-5,
        print_stats=False,
        loudness_range_target=7,
        keep_loudness_range_target=True,
        keep_lra_above_loudness_range_target=False,
        true_peak=0,
        offset=0,
        lower_only=False,
        auto_lower_loudness_target=True,
        dual_mono=False,
        dynamic=False,
        audio_codec="aac",
        audio_bitrate=128000,
        sample_rate=None,
        audio_channels=None,
        keep_original_audio=False,
        pre_filter=None,
        post_filter=None,
        video_codec="copy",
        video_disable=False,
        subtitle_disable=True,
        metadata_disable=True,
        chapters_disable=True,
        extra_input_options=None,
        extra_output_options=["-movflags", "faststart"],
        output_format=None,
        dry_run=False,
        debug=False,
        progress=False,
    )
    normalizer.add_media_file(str(input_file), str(output_file))
    normalizer.run_normalization()

    print(f"音量正規化が完了: {output_file.name}")


def find_files(path: Path, suffix: str) -> Iterator[Path]:
    """指定されたパスから指定された拡張子のファイルを再帰的に検索"""
    suffix = suffix.lower()
    if path.is_file() and path.suffix.lower() == suffix:
        yield path
    elif path.is_dir():
        yield from (
            item
            for item in path.rglob("*")
            if item.is_file() and item.suffix.lower() == suffix
        )


def format_command(cmd: List[str]) -> str:
    """コマンドをPowerShell用に整形"""
    formatted_cmd = []
    for arg in cmd:
        # パス文字を含む引数はクォートで囲む
        if any(c in arg for c in r"\/.:"):
            formatted_cmd.append(f'"{arg}"')
        else:
            formatted_cmd.append(arg)

    return " ".join(formatted_cmd) + "\n"
