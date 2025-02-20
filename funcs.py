import os
import subprocess
from pathlib import Path
from typing import Iterator, List, Optional

from dotenv import load_dotenv
from ffmpeg_normalize import FFmpegNormalize

load_dotenv()
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"


def normalize_audio(input_file: Path, output_file: Path) -> None:
    """音量を正規化"""

    print(f"音量正規化開始: {input_file.name}")

    normalizer = FFmpegNormalize(
        normalization_type="ebu",
        target_level=-5,
        print_stats=TEST_MODE,
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
        progress=TEST_MODE,
    )
    normalizer.add_media_file(str(input_file), str(output_file))
    normalizer.run_normalization()

    print(f"音量正規化完了: {output_file.name}")


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


def find_video_files(path: Path) -> Iterator[Path]:
    """指定されたパスから動画ファイルを再帰的に検索"""

    if path.is_file() and is_video_file(path):
        yield path
    elif path.is_dir():
        yield from (
            item for item in path.rglob("*") if item.is_file() and is_video_file(item)
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


def run_command(
    cmd: List[str],
    description: str = "",
    capture_output: bool = False,
    path: Optional[Path] = None,
    silent: bool = False,
) -> Optional[subprocess.CompletedProcess]:
    """コマンドを実行"""

    if TEST_MODE:
        print(f"[テストモード] {description}")
        print(f"実行コマンド:\n{format_command(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            if not silent:
                print(f"エラー: {description}失敗: {path}")
                print(f"エラー内容:\n{result.stderr}")
            return None
        return result
    except FileNotFoundError as e:
        print(f"エラー: コマンドが見つかりません: {cmd[0]}")
        print(f"エラー内容: {str(e)}")
        return None
    except subprocess.SubprocessError as e:
        if not silent:
            print(f"エラー: {description}失敗: {path}")
            print(f"エラー内容: {str(e)}")
        return None


def is_video_file(file_path: Path) -> bool:
    """ファイルが動画かどうかを判断する"""
    if not file_path.is_file():
        return False

    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-select_streams",
        "v:0",  # 最初のビデオストリームを選択
        "-show_entries",
        "stream=codec_type",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(file_path),
    ]

    result = run_command(
        cmd=cmd,
        description="動画ファイルの判定",
        capture_output=True,
        path=file_path,
        silent=True,
    )
    if result is None:
        return False

    # 出力が"video"であれば動画ファイル
    return result.stdout.strip() == "video"
