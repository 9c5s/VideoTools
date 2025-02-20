import argparse
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from yt_dlp import YoutubeDL

from utils import normalize_audio

# .envファイルから環境変数を読み込む
load_dotenv()

# 環境変数から設定を読み込む
DOWNLOAD_ARCHIVE_PATH = (
    Path(os.getenv("DOWNLOAD_ARCHIVE_PATH", ""))
    if os.getenv("DOWNLOAD_ARCHIVE_PATH")
    else None
)


def download_video(url: str, output_dir: Path) -> bool:
    """yt-dlpを使用して動画をダウンロードする"""
    # 一時ディレクトリを作成
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        ydl_opts: Dict[str, Any] = {
            "format_sort": ["codec:avc:aac", "res:1080", "fps:60", "hdr:sdr"],
            "format": "bv+ba",
            "outtmpl": str(
                temp_path
                / "%(title)s_%(height)s_%(fps)s_%(vcodec.:4)s_(%(id)s).%(ext)s"
            ),
        }

        # DOWNLOAD_ARCHIVE_PATHが設定されており、かつファイルが存在する場合のみdownload_archiveオプションを追加
        if DOWNLOAD_ARCHIVE_PATH and DOWNLOAD_ARCHIVE_PATH.exists():
            ydl_opts["download_archive"] = str(DOWNLOAD_ARCHIVE_PATH)

        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

                # ダウンロードしたファイルを処理
                for video_file in temp_path.glob("*"):
                    # 音量正規化を実行(直接output_dirに出力)
                    normalize_audio(video_file, output_dir / video_file.name)

            return True
        except Exception as e:
            print(f"ダウンロード中にエラーが発生しました: {str(e)}")
            return False


def main() -> None:
    parser = argparse.ArgumentParser(description="動画をダウンロードします")
    parser.add_argument("url", help="ダウンロードする動画のURL")
    args = parser.parse_args()

    output_dir = Path.cwd()

    if download_video(args.url, output_dir):
        print("ダウンロードが完了しました")
    else:
        print("ダウンロードに失敗しました")


if __name__ == "__main__":
    main()
