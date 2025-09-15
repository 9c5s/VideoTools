import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import List, Tuple

from pathvalidate import sanitize_filename

from utils import (
    TEST_MODE,
    find_files,
    format_time,
    normalize_audio,
    run_command,
)


def check_dependencies(commands: List[str]) -> bool:
    """必要な外部コマンドが利用可能か確認"""
    missing = []
    for cmd in commands:
        if not shutil.which(cmd):
            missing.append(cmd)

    if missing:
        print("以下のコマンドが見つかりません:")
        for cmd in missing:
            print(f"- {cmd}")
        return False
    return True


def is_default_chapter_name(name: str) -> bool:
    """デフォルトのチャプター名かどうかを判定"""
    pattern = r"^(Chapter|ブックマーク) \d+$"
    return bool(re.match(pattern, name))


def parse_chapter_file(text: str) -> List[Tuple[int, str]]:
    """チャプターファイルのテキストを解析"""
    chapters = []
    current_number = None

    for line in text.splitlines():
        if not line:
            continue

        if line.startswith("CHAPTER") and "NAME" not in line:
            # 例: CHAPTER01=00:00:00.000
            current_number = int(line[7:9])
        elif line.startswith("CHAPTER") and "NAME" in line:
            # 例: CHAPTER01NAME=Chapter 01
            chapter_name = line.split("=", 1)[1]
            if not is_default_chapter_name(chapter_name):
                chapters.append((current_number, chapter_name))

    return chapters


def get_chapters(mkv_file: Path) -> List[Tuple[int, str]]:
    """mkvファイルからチャプター情報を取得"""
    result = run_command(
        cmd=["mkvextract", str(mkv_file), "chapters", "-s"],
        description="チャプター情報取得",
        capture_output=True,
        path=mkv_file,
    )
    if result is None:
        return []

    return parse_chapter_file(result.stdout)


def get_temp_path(suffix: str) -> Path:
    """一時ファイルのパスを生成"""
    # 一時ファイルを作成（ファイル自体は作成されるが内容は空）
    temp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    temp_file.close()
    return Path(temp_file.name)


def get_handbrake_command(
    input_file: Path, temp_output: Path, chapter_number: int
) -> List[str]:
    """HandBrakeコマンドを生成"""
    cmd = ["HandBrakeCLI"]

    # ソースオプション
    cmd.extend(["--input", str(input_file)])
    cmd.extend(["--chapters", f"{chapter_number}"])
    cmd.extend(["--previews", "0:0"])  # プレビュー画像を生成しない

    # 出力先オプション
    cmd.extend(["--output", str(temp_output)])
    cmd.extend(["--format", "av_mp4"])  # コンテナフォーマット
    cmd.extend(["--no-markers"])  # チャプターマーカー無し
    cmd.extend(["--optimize"])  # MOOVアトムを先頭に配置
    cmd.extend(["--no-ipod-atom"])  # iPod 5Gアトムを無効化
    cmd.extend(["--align-av"])  # AV同期

    # ビデオオプション
    cmd.extend(["--encoder", "nvenc_h264" if TEST_MODE else "x264"])
    cmd.extend(["--encoder-preset", "fastest" if TEST_MODE else "medium"])
    if not TEST_MODE:
        cmd.extend(["--encoder-tune", "film"])  # x264用
    cmd.extend(["--encoder-profile", "high"])
    cmd.extend(["--encoder-level", "auto"])
    cmd.extend(["--vb", "6000"])
    if not TEST_MODE:
        cmd.extend(["--multi-pass", "--turbo"])  # x264用
    cmd.extend(["--cfr"])  # ソースの平均フレームレートで固定
    # cmd.extend(["--enable-hw-decoding", "nvdec"])

    # オーディオオプション
    cmd.extend(["--first-audio"])  # 最初のトラックのみ選択
    cmd.extend(["--aencoder", "flac24"])

    # 画像オプション
    cmd.extend(["--width", "1920"])
    cmd.extend(["--height", "1080"])
    cmd.extend(["--crop-mode", "none"])
    cmd.extend(["--non-anamorphic"])
    # cmd.extend(["--color-matrix", "709"])  # 要調査

    # フィルターオプション
    cmd.extend(["--no-comb-detect"])
    cmd.extend(["--no-deinterlace"])
    cmd.extend(["--no-bwdif"])
    cmd.extend(["--no-decomb"])
    cmd.extend(["--no-detelecine"])
    cmd.extend(["--no-hqdn3d"])
    cmd.extend(["--no-nlmeans"])
    cmd.extend(["--no-chroma-smooth"])
    cmd.extend(["--no-unsharp"])
    cmd.extend(["--no-lapsharp"])
    cmd.extend(["--no-deblock"])
    cmd.extend(["--colorspace", "bt709"])
    cmd.extend(["--no-grayscale"])

    # 字幕オプション
    cmd.extend(["--subtitle", "none"])

    return cmd


def extract_chapter(
    input_file: Path,
    output_file: Path,
    chapter_number: int,
) -> bool:
    """HandBrakeを使用して特定のチャプターを抽出してmp4に変換し、音量を正規化"""
    # 一時ファイルのパスを生成
    temp_output = get_temp_path(output_file.suffix)

    # HandBrakeコマンドを生成
    handbrake_cmd = get_handbrake_command(input_file, temp_output, chapter_number)

    try:
        # HandBrakeでエンコード
        result = run_command(
            cmd=handbrake_cmd,
            description="エンコード",
            capture_output=True,
            path=input_file,
        )
        if result is None:
            if temp_output.exists():
                temp_output.unlink()
            return False

        # 音量を正規化
        try:
            normalize_audio(temp_output, output_file)
        except Exception as e:
            print(f"エラー: 音量正規化に失敗: {output_file}")
            print(f"エラー内容: {str(e)}")
            if output_file.exists():
                output_file.unlink()
            return False

        return True
    finally:
        try:
            temp_output.unlink()
        except FileNotFoundError:
            pass  # ファイルが既に削除されている場合は無視


def process_mkv_file(mkv_file: Path) -> bool:
    """MKVファイルを処理"""
    print(f"\n処理開始: {mkv_file.name}")
    start_time = time.time()

    chapters = get_chapters(mkv_file)
    if not chapters:
        print("チャプター情報が見つかりませんでした")
        return False

    success = True
    total = len(chapters)
    for i, (chapter_number, chapter_name) in enumerate(chapters, 1):
        chapter_start_time = time.time()

        safe_name = sanitize_filename(chapter_name)
        output_file = mkv_file.parent / f"{safe_name}.mp4"

        if output_file.exists():
            print(f"\nスキップ [{i}/{total}]: '{chapter_name}' は既に存在します")
            continue

        print(f"\nエンコード中 [{i}/{total}]: '{chapter_name}'")
        if not extract_chapter(mkv_file, output_file, chapter_number):
            success = False

        # チャプターの処理時間を表示
        chapter_elapsed_time = time.time() - chapter_start_time
        print(f"チャプター処理時間: {format_time(chapter_elapsed_time)}")

    # 全体の処理時間を表示
    total_elapsed_time = time.time() - start_time
    print(f"\n全体処理時間: {format_time(total_elapsed_time)}")

    return success


def main() -> None:
    if len(sys.argv) < 2:
        print("MKVファイルまたはフォルダをドラッグ&ドロップしてください")
        input("Enterキーで終了")
        return

    required_commands = ["HandBrakeCLI", "mkvextract", "ffmpeg"]
    if not check_dependencies(required_commands):
        input("Enterキーで終了")
        return

    success = True
    for path_str in sys.argv[1:]:
        for mkv_file in find_files(Path(path_str), ".mkv"):
            try:
                if not process_mkv_file(mkv_file):
                    success = False
            except Exception as e:
                print(f"エラー: {mkv_file.name} の処理中に問題が発生しました")
                print(f"詳細: {e}")
                success = False

    print("\n処理が完了しました")
    if not success:
        print("※ 一部のファイルでエラーが発生しました")
    input("Enterキーで終了")


if __name__ == "__main__":
    main()
