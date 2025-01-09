import os
import shutil
import subprocess
import sys
import tempfile

from yt_dlp import YoutubeDL


def trim_silence(
    input_file, output_file, silence_threshold="-50dB", min_silence_duration=0.5
):
    """
    動画ファイルの前後の無音部分を除去する

    Args:
        input_file: 入力動画ファイルのパス
        output_file: 出力動画ファイルのパス
        silence_threshold: 無音と判定する音量のしきい値（デフォルト: -50dB）
        min_silence_duration: 無音と判定する最小の継続時間（秒）
    """
    temp_wav = None
    try:
        # 一時ファイルの作成
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
            temp_wav_path = temp_wav.name

        # WAVに変換
        wav_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-v",
            "warning",
            "-i",
            input_file,
            "-vn",
            "-map",
            "0:a:0",
            "-c:a",
            "pcm_s16le",
            "-f",
            "wav",
            temp_wav_path,
        ]
        subprocess.run(wav_cmd)

        # 無音部分を検出
        detect_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-i",
            temp_wav_path,
            "-af",
            f"silencedetect=noise={silence_threshold}:d={min_silence_duration}",
            "-f",
            "null",
            "-",
        ]
        result = subprocess.run(detect_cmd, capture_output=True, text=True)

        # 無音部分の開始・終了時間を抽出
        silence_starts = []
        silence_ends = []
        for line in result.stderr.split("\n"):
            if "silence_start" in line:
                silence_starts.append(
                    float(line.split("silence_start: ")[1].split()[0])
                )
            elif "silence_end" in line:
                silence_ends.append(float(line.split("silence_end: ")[1].split()[0]))

        if not silence_starts or not silence_ends:
            print("無音部分が検出されませんでした")
            shutil.copy2(input_file, output_file)
            return

        # 最初の無音以外の部分の開始時間と最後の無音以外の部分の終了時間を取得
        start_time = silence_ends[0]
        end_time = silence_starts[-1]

        # 時間をカンマ区切りの文字列に変換
        time_range = f"{start_time},{end_time}"

        # ANSIエスケープシーケンスを使用して赤字で表示
        print(f"\033[91m{time_range}\033[0m")

        # 動画のトリミング
        subprocess.run(["smartcut.exe", input_file, output_file, "--keep", time_range])

    except Exception as e:
        print(f"無音トリミング処理中にエラーが発生しました: {e}")
        raise
    finally:
        # 一時ファイルの確実な削除
        if temp_wav is not None:
            try:
                if os.path.exists(temp_wav.name):
                    os.unlink(temp_wav.name)
            except OSError as e:
                print(f"一時ファイルの削除中にエラーが発生しました: {e}")


def download_and_trim_video(url, output_path=None):
    """
    URLから動画をダウンロードし、無音部分を除去する

    Args:
        url: ダウンロードする動画のURL
        output_path: 出力ファイルパス（省略時は現在のディレクトリ）
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # yt-dlpの設定
        ydl_opts = {
            "format_sort": ["codec:avc:aac", "res:1080", "fps:60", "hdr:sdr"],
            "format": "bv+ba",
            "outtmpl": os.path.join(
                temp_dir, "%(title)s_%(height)s_%(fps)s_%(vcodec.:4)s_(%(id)s).%(ext)s"
            ),
            "postprocessor_args": {"Merger+ffmpeg_o1": ["-map_metadata", "-1"]},
        }

        # 動画のダウンロード
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)

        # 出力パスの設定
        if output_path is None:
            output_path = os.path.basename(downloaded_file)

        # 無音部分の除去
        trim_silence(downloaded_file, output_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法: python videoDownloader.py <URL> [出力ファイルパス]")
        sys.exit(1)

    url = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        download_and_trim_video(url, output_path)
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        sys.exit(1)
