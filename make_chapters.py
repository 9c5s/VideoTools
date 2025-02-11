import sys
import subprocess
import shutil
import csv
import xml.etree.ElementTree as ET
from pathlib import Path


def check_mkvextract() -> bool:
    """mkvextractコマンドが利用可能かチェックする"""
    if not shutil.which("mkvextract"):
        print("エラー: mkvextractが見つかりません")
        print("MKVToolNixをインストールし、mkvextractにパスを通してください")
        return False
    return True


def create_chapter_csv(xml_file: Path) -> None:
    """XMLファイルからチャプター情報を抽出してCSVファイルを作成する"""
    csv_file = xml_file.with_suffix(".csv")

    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()

        # ChapterAtomからTimeStartとStringを抽出
        chapters = []
        for chapter in root.findall(".//ChapterAtom"):
            time_start = chapter.find("ChapterTimeStart").text
            chapter_string = chapter.find(".//ChapterString").text
            chapters.append([time_start, chapter_string])

        # CSVファイルに書き出し
        with csv_file.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["TimeStart", "ChapterName"])
            writer.writerows(chapters)

        print(f'チャプター情報を"{csv_file.name}"に保存しました')

    except Exception as e:
        print(f"CSVファイルの作成中にエラーが発生しました: {str(e)}")


def extract_chapters(mkv_file: Path) -> None:
    """MKVファイルからチャプター情報を抽出してXMLファイルに保存する"""
    if not mkv_file.suffix.lower() == ".mkv":
        print(f'"{mkv_file.name}"はmkvファイルではありません')
        return

    output_file = mkv_file.with_name(f"{mkv_file.stem}_chapters.xml")
    print(f'"{mkv_file.name}"からチャプター情報を抽出しています...')

    try:
        result = subprocess.run(
            ["mkvextract", str(mkv_file), "chapters", str(output_file)],
            encoding="utf-8",
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            if output_file.exists():
                print(f'チャプター情報を"{output_file.name}"に保存しました')
                # XMLファイルからCSVを作成
                create_chapter_csv(output_file)
            else:
                print(f'"{mkv_file.name}"にはチャプター情報が存在しません')
        else:
            print(f'エラーが発生しました: "{mkv_file.name}"')
            if result.stderr:
                print(f"エラー詳細: {result.stderr.strip()}")
    except Exception as e:
        print(f'エラーが発生しました: "{mkv_file.name}" - {str(e)}')
    print()


def process_path(path: Path) -> None:
    """パスを処理し、ファイルまたはフォルダ内のMKVファイルを処理する"""
    if path.is_file():
        extract_chapters(path)
    elif path.is_dir():
        # フォルダ内のすべてのMKVファイルを再帰的に処理
        for mkv_file in path.rglob("*.mkv"):
            extract_chapters(mkv_file)


def main():
    if not check_mkvextract():
        return

    if len(sys.argv) < 2:
        print("MKVファイルまたはフォルダをドラッグ＆ドロップしてください")
        return

    for path in sys.argv[1:]:
        process_path(Path(path))


if __name__ == "__main__":
    main()
