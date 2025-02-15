import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

from pathvalidate import sanitize_filename


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
    """デフォルトのチャプター名（Chapter XX）かどうかを判定"""
    pattern = r"^Chapter \d{2}$"
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


def run_command(
    cmd: List[str], description: str, path: Path
) -> Optional[subprocess.CompletedProcess]:
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
            print(f"エラー: {description}失敗: {path}")
            print(f"エラー内容:\n{result.stderr}")
            return None
        return result
    except subprocess.SubprocessError as e:
        print(f"エラー: {description}失敗: {path}")
        print(f"エラー内容: {str(e)}")
        return None


def get_chapters(mkv_file: Path) -> List[Tuple[int, str]]:
    """mkvファイルからチャプター情報を取得"""
    result = run_command(
        ["mkvextract", str(mkv_file), "chapters", "-s"],
        "チャプター情報取得",
        mkv_file,
    )
    if result is None:
        return []

    return parse_chapter_file(result.stdout)


def format_handbrake_command(cmd: List[str]) -> str:
    """コマンドをPowerShell用に整形"""
    # パスを含む引数をダブルクォートで囲む
    formatted_cmd = []
    for arg in cmd:
        # パス文字を含む引数はクォートで囲む
        if any(c in arg for c in r"\/.:"):
            formatted_cmd.append(f'"{arg}"')
        else:
            formatted_cmd.append(arg)

    return " ".join(formatted_cmd)


def extract_chapter(
    input_file: Path,
    output_file: Path,
    chapter_number: int,
) -> bool:
    """HandBrakeを使用して特定のチャプターを抽出してmp4に変換"""
    cmd = [
        "HandBrakeCLI",
        # ソースオプション
        "--input",
        str(input_file),
        "--chapters",
        f"{chapter_number}",
        "--previews",
        "0:0",  # プレビュー画像を生成しない
        # 出力先オプション
        "--output",
        str(output_file),
        "--format",  # コンテナフォーマット
        "av_mp4",
        "--no-markers",  # チャプターマーカー無し
        "--optimize",  # MOOVアトムを先頭に配置
        "--no-ipod-atom",  # iPod 5Gアトムを無効化
        "--align-av",  # AV同期
        # ビデオオプション
        "--encoder",
        "nvenc_h264",
        "--encoder-preset",
        "fastest",
        # "--encoder-tune",  # x264用
        # "film",  # x264用
        "--encoder-profile",
        "high",
        "--encoder-level",
        "auto",
        "--vb",
        "6000",
        # "--multi-pass",  # x264用
        # "--turbo",  # x264用
        "--cfr",  # ソースの平均フレームレートで固定
        "--enable-hw-decoding",
        "nvdec",
        # オーディオオプション
        "--first-audio",
        "--aencoder",
        "av_aac",
        "--ab",
        "128",
        "--mixdown",
        "stereo",
        "--normalize-mix",
        "1",  # 正規化有効
        "--arate",
        "48",
        "--drc",  # ダイナミックレンジ圧縮を適用
        "2.5",
        # 画像オプション
        "--width",
        "1920",
        "--height",
        "1080",
        "--crop-mode",
        "none",
        "--non-anamorphic",
        # "--color-matrix",  # 要不要調査
        # "709",
        # フィルターオプション
        "--no-comb-detect",
        "--no-deinterlace",
        "--no-bwdif",
        "--no-decomb",
        "--no-detelecine",
        "--no-hqdn3d",
        "--no-nlmeans",
        "--no-chroma-smooth",
        "--no-unsharp",
        "--no-lapsharp",
        "--no-deblock",
        "--colorspace",
        "bt709",
        "--no-grayscale",
        # 字幕オプション
        "--subtitle",
        "none",
    ]

    # PowerShell用コマンドを表示
    print("\nテスト用コマンド:")
    print(format_handbrake_command(cmd))
    print()

    result = run_command(cmd, "エンコード", input_file)
    if result is None:
        if output_file.exists():
            output_file.unlink()
        return False
    return True


def find_mkv_files(path: Path) -> Iterator[Path]:
    """指定されたパスからMKVファイルを再帰的に検索"""
    if path.is_file() and path.suffix.lower() == ".mkv":
        yield path
    elif path.is_dir():
        yield from (
            item
            for item in path.rglob("*")
            if item.is_file() and item.suffix.lower() == ".mkv"
        )


def process_mkv_file(mkv_file: Path) -> bool:
    """MKVファイルを処理"""
    print(f"\n処理開始: {mkv_file.name}")
    chapters = get_chapters(mkv_file)
    if not chapters:
        print("チャプター情報が見つかりませんでした")
        return False

    success = True
    total = len(chapters)
    for i, (chapter_number, chapter_name) in enumerate(chapters, 1):
        safe_name = sanitize_filename(chapter_name)
        output_file = mkv_file.parent / f"{safe_name}.mp4"

        if output_file.exists():
            print(f"スキップ [{i}/{total}]: '{chapter_name}' は既に存在します")
            continue

        print(f"抽出中 [{i}/{total}]: '{chapter_name}'")
        if not extract_chapter(mkv_file, output_file, chapter_number):
            success = False

    return success


def main() -> None:
    if len(sys.argv) < 2:
        print("MKVファイルまたはフォルダをドラッグ&ドロップしてください")
        input("Enterキーで終了")
        return

    required_commands = ["HandBrakeCLI", "mkvextract"]
    if not check_dependencies(required_commands):
        input("Enterキーで終了")
        return

    success = True
    for path_str in sys.argv[1:]:
        for mkv_file in find_mkv_files(Path(path_str)):
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
