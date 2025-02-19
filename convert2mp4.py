import logging
import subprocess
import sys
import tempfile
from multiprocessing import Pool
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


def get_handbrake_command(path: Path, tmp_path: Path) -> Sequence[str]:
    """HandBrakeコマンドを生成（エンコード用）"""
    return [
        "HandBrakeCLI",
        "--force",
        "--input",
        str(path),
        "--output",
        str(tmp_path),
        "--format",
        "av_mp4",
        "--optimize",
        "--align-av",
        "--markers",
        "--encoder",
        "nvenc_av1_10bit",
        "--encoder-preset",
        "slowest",
        "--quality",
        "40",
        "--aencoder",
        "aac",
        "--ab",
        "128",
        "--mixdown",
        "stereo",
    ]


def get_ffmpeg_copy_command(path: Path, tmp_path: Path) -> Sequence[str]:
    """FFmpegコマンドを生成（コピー用）"""
    return [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        str(path),
        "-c",
        "copy",
        str(tmp_path),
    ]


def get_ffmpeg_command(tmp_path: Path, output_path: Path) -> Sequence[str]:
    """FFmpegコマンドを生成（メタデータ除去用）"""
    return [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(tmp_path),
        "-map_metadata",
        "-1",
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(output_path),
    ]


def run_command(cmd: Sequence[str], description: str, path: Path) -> bool:
    """コマンドを実行"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            logger.error(f"エラー: {description}失敗: {path}")
            logger.error(f"エラー内容:\n{result.stderr}")
            return False
        return True
    except subprocess.SubprocessError as e:
        logger.error(f"エラー: {description}失敗: {path}")
        logger.error(f"エラー内容: {str(e)}")
        return False


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

    # 一時ファイルを作成
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)

    try:
        # 変換処理
        cmd = (
            get_handbrake_command(path, tmp_path)
            if needs_encode(video_codec, audio_codec)
            else get_ffmpeg_copy_command(path, tmp_path)
        )
        description = (
            "エンコード" if needs_encode(video_codec, audio_codec) else "コピー"
        )

        if not run_command(cmd, description, path):
            return False

        # エンコード後のファイルサイズを確認
        if not tmp_path.exists() or tmp_path.stat().st_size == 0:
            logger.error(
                f"エラー: エンコード後のファイルが存在しないか空です: {tmp_path}"
            )
            return False

        # メタデータ除去
        if not run_command(
            get_ffmpeg_command(tmp_path, output_path), "メタデータ除去", path
        ):
            return False

        logger.info(f"変換成功: {path}")
        return True

    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception as e:
            logger.error(f"一時ファイルの削除に失敗: {str(e)}")


def process_single_file(args: Tuple[int, Path, int]) -> None:
    """単一のビデオファイルを処理"""
    try:
        index, video_file, total_files = args
        logger.info(f"\n[{index + 1}/{total_files}] 処理中...")
        if video_info := get_video_info(video_file):
            convert_video(*video_info)
    except Exception as e:
        logger.error(f"ファイル処理中にエラーが発生: {str(e)}")


def process_paths(paths: Sequence[str]) -> None:
    """パスリストを処理"""
    try:
        video_files = [
            video_file
            for path_str in paths
            for video_file in find_video_files(Path(path_str))
        ]

        if not video_files:
            logger.info("変換対象のファイルが見つかりません")
            return

        total_files = len(video_files)
        logger.info(f"合計 {total_files} 個のファイルを処理します")

        # 処理対象のファイルリストを準備
        process_args = [(i, f, total_files) for i, f in enumerate(video_files)]

        # 4プロセスで並列処理
        with Pool(processes=4) as pool:
            pool.map(process_single_file, process_args)

    except Exception as e:
        logger.error(f"エラーが発生しました: {str(e)}")


def wait_for_key() -> None:
    """キー入力を待機"""
    try:
        input("\n任意のキーを押して終了してください...")
    except (EOFError, KeyboardInterrupt):
        pass


def main() -> None:
    """メイン処理"""
    try:
        if len(sys.argv) < 2:
            print(
                "使用方法: python convert2mp4.py <入力ファイル/フォルダ> [入力ファイル/フォルダ...]"
            )
            sys.exit(1)

        process_paths(sys.argv[1:])
        wait_for_key()

    except Exception as e:
        logger.error(f"予期せぬエラーが発生しました: {str(e)}")
        wait_for_key()


if __name__ == "__main__":
    main()
