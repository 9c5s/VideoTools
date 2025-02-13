import logging
import subprocess
import sys
from pathlib import Path
from typing import Iterator, Optional, Sequence, Tuple

# ロギングの設定
logging.basicConfig(format="%(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# 対応する動画ファイルの拡張子
VIDEO_EXTENSIONS = {
    ".mp4",
    ".avi",
    ".mkv",
    ".mov",
    ".wmv",
    ".flv",
    ".webm",
    ".m4v",
    ".ts",
}

# 変換不要なコーデック
SUPPORTED_VIDEO_CODECS = {"h264", "hevc", "av1"}
SUPPORTED_AUDIO_CODECS = {"aac", "mp3"}


def get_output_path(input_path: Path) -> Path:
    """出力ファイルのパスを取得"""
    return input_path.with_suffix(".mp4")


def needs_encode(video_codec: str, audio_codec: str) -> bool:
    """再エンコードが必要かどうかを判定"""
    return (
        video_codec not in SUPPORTED_VIDEO_CODECS
        or audio_codec not in SUPPORTED_AUDIO_CODECS
    )


def find_video_files(path: Path) -> Iterator[Path]:
    """動画ファイルを再帰的に検索"""
    if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
        yield path
    elif path.is_dir():
        yield from (
            item
            for item in path.rglob("*")
            if item.is_file() and item.suffix.lower() in VIDEO_EXTENSIONS
        )


def get_codec_info(path: Path, stream_type: str) -> str:
    """コーデック情報を取得"""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                stream_type,
                "-show_entries",
                "stream=codec_name",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() or "unknown"
    except subprocess.SubprocessError:
        return "unknown"


def get_video_info(path: Path) -> Optional[Tuple[Path, str, str]]:
    """ビデオファイルの情報を取得"""
    if not path.is_file():
        logger.error(f"エラー: ファイルが見つかりません: {path}")
        return None

    vcodec = get_codec_info(path, "v:0")
    if vcodec == "unknown":
        logger.error(f"エラー: コーデック情報を取得できません: {path}")
        return None

    return path, vcodec, get_codec_info(path, "a:0")


def get_ffmpeg_command(path: Path, video_codec: str, audio_codec: str) -> Sequence[str]:
    """FFmpegコマンドを生成"""
    output_path = get_output_path(path)
    common_args = [
        "ffmpeg",
        "-hide_banner",
        "-v",
        "error",
        "-stats",
        "-i",
        str(path),
        "-map_metadata",
        "-1",
        "-movflags",
        "+faststart",
    ]

    if needs_encode(video_codec, audio_codec):
        encode_args = [
            "-c:v",
            "av1_nvenc",
            "-preset",
            "p7",
            "-tune",
            "hq",
            "-c:a",
            "aac",
        ]
    else:
        encode_args = ["-c", "copy"]

    return [*common_args, *encode_args, str(output_path)]


def convert_video(path: Path, video_codec: str, audio_codec: str) -> bool:
    """ビデオを変換"""
    output_path = get_output_path(path)
    if output_path.exists():
        logger.info(f"スキップ: 出力ファイルが存在します: {output_path}")
        return True

    logger.info(f"コーデック - ビデオ: {video_codec}, オーディオ: {audio_codec}")
    logger.info(
        f"{'エンコード' if needs_encode(video_codec, audio_codec) else 'コンテナ変換'}中: {path}"
    )

    try:
        cmd = get_ffmpeg_command(path, video_codec, audio_codec)
        result = subprocess.run(cmd)
        if result.returncode != 0:
            logger.error(f"エラー: 変換失敗: {path}")
            return False

        logger.info(f"変換成功: {path}")
        return True

    except subprocess.SubprocessError as e:
        logger.error(f"エラー: 変換失敗: {path}")
        logger.error(f"エラー内容: {str(e)}")
        return False


def process_paths(paths: Sequence[str]) -> None:
    """パスリストを処理"""
    video_files = [
        video_file
        for path_str in paths
        for video_file in find_video_files(Path(path_str))
    ]

    if not video_files:
        logger.info("変換対象のファイルが見つかりません")
        return

    for i, video_file in enumerate(video_files, 1):
        logger.info(f"\n[{i}/{len(video_files)}] 処理中...")
        if video_info := get_video_info(video_file):
            convert_video(*video_info)


def main() -> None:
    """メイン処理"""
    if len(sys.argv) < 2:
        print(
            "使用方法: python convert2mp4.py <入力ファイル/フォルダ> [入力ファイル/フォルダ...]"
        )
        sys.exit(1)

    process_paths(sys.argv[1:])

    print("\n処理が完了しました。任意のキーを押して終了してください...")
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    main()
