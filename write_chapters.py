import csv
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List


def update_chapter_xml(csv_path: Path, xml_path: Path) -> None:
    """CSVの内容でXMLのチャプター名を更新する"""
    # CSVからチャプター情報を読み取る
    chapters: Dict[str, str] = {}  # TimeStart をキーにしてChapterNameを格納
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            chapters[row["TimeStart"]] = row["ChapterName"]

    # 既存のXMLを読み込む
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # 各チャプターを検索して更新
    for chapter_atom in root.findall(".//ChapterAtom"):
        time_start = chapter_atom.find("ChapterTimeStart").text
        if time_start not in chapters:
            continue

        chapter_string = chapter_atom.find("./ChapterDisplay/ChapterString")
        new_name = chapters[time_start]
        if chapter_string.text != new_name:
            chapter_string.text = new_name

    # XMLを保存
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)
    print("チャプターファイルを更新しました")


def write_chapters_to_mkv(mkv_path: Path, xml_path: Path, csv_path: Path) -> None:
    """MKVファイルにチャプター情報を書き込む"""
    try:
        subprocess.run(
            ["mkvpropedit", str(mkv_path), "--chapters", str(xml_path)], check=True
        )
        print("チャプターの書き込みが完了しました")

        # チャプターファイルを削除
        xml_path.unlink()
        csv_path.unlink()
        print("チャプターファイルを削除しました")

    except subprocess.CalledProcessError as e:
        print(f"エラー: チャプターの書き込みに失敗しました: {e}")
    except FileNotFoundError:
        print(
            "エラー: mkvpropeditが見つかりません。MKVToolNixがインストールされているか確認してください"
        )


def get_chapter_paths(mkv_path: Path) -> tuple[Path, Path]:
    """MKVファイルに対応するチャプターファイルのパスを取得する"""
    base_path = mkv_path.with_suffix("")
    csv_path = base_path.with_name(f"{base_path.name}_chapters.csv")
    xml_path = base_path.with_name(f"{base_path.name}_chapters.xml")
    return csv_path, xml_path


def check_required_files(csv_path: Path, xml_path: Path) -> bool:
    """必要なファイルが揃っているかチェックする"""
    if not csv_path.exists():
        print(f"スキップ: チャプター情報ファイル {csv_path.name} が見つかりません")
        return False

    if not xml_path.exists():
        print(f"スキップ: チャプターファイル {xml_path.name} が見つかりません")
        return False

    return True


def process_mkv_file(mkv_path: Path, index: int, total: int) -> None:
    """MKVファイルのチャプター情報を処理する"""
    print(f"\n処理: [{index}/{total}] {mkv_path.name}")

    # CSVとXMLのパスを設定
    csv_path, xml_path = get_chapter_paths(mkv_path)

    # 必要なファイルが揃っているかチェック
    if not check_required_files(csv_path, xml_path):
        return

    # XMLファイルを更新
    update_chapter_xml(csv_path, xml_path)

    # MKVファイルにチャプターを書き込む
    write_chapters_to_mkv(mkv_path, xml_path, csv_path)


def find_mkv_files(path: Path) -> List[Path]:
    """指定されたパスからMKVファイルを再帰的に検索する"""
    if path.is_file():
        return [path] if path.suffix.lower() == ".mkv" else []

    mkv_files = []
    for item in path.rglob("*.mkv"):
        mkv_files.append(item)
    return mkv_files


def main() -> None:
    if len(sys.argv) < 2:
        print("使用方法: write_chapters.py <MKVファイル または フォルダ>")
        return

    # 全てのパスからMKVファイルを収集
    mkv_files: List[Path] = []
    for arg in sys.argv[1:]:
        path = Path(arg)
        if not path.exists():
            print(f"エラー: {path} が見つかりません")
            continue

        # MKVファイルを検索して追加
        files = find_mkv_files(path)
        if not files:
            print(f"スキップ: {path} にMKVファイルが見つかりません")
            continue
        mkv_files.extend(files)

    if not mkv_files:
        print("処理対象のMKVファイルが見つかりません")
        return

    # 収集した全てのMKVファイルを処理
    print(f"\n合計 {len(mkv_files)} 個のMKVファイルを処理します")
    for i, mkv_file in enumerate(mkv_files, 1):
        process_mkv_file(mkv_file, i, len(mkv_files))

    print("\n全ての処理が完了しました")


if __name__ == "__main__":
    main()
