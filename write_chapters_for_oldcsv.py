import sys
import subprocess
import csv
import xml.etree.ElementTree as ET
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Union


def timestamp_to_seconds(timestamp: str) -> float:
    """00:00:00.000000000 形式のタイムスタンプを秒数に変換"""
    h, m, s = timestamp.split(":")
    # 小数点以下6桁で丸め
    total_seconds = float(h) * 3600 + float(m) * 60 + float(s)
    return round(total_seconds, 6)


def read_chapters_from_csv(csv_path: Path) -> List[Dict[str, Union[float, str]]]:
    """CSVファイルからチャプター情報を読み込む"""
    chapters = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            start_time = float(row["start"])
            # タイトルからYYMMDD_形式のプレフィックスを削除
            title = row["title"]
            if len(title) > 7 and title[6] == "_" and title[:6].isdigit():
                title = title[7:]
            chapters.append({"start": start_time, "title": title})
    return chapters


def update_xml_chapters(
    xml_path: Path, chapters: List[Dict[str, Union[float, str]]]
) -> None:
    """XMLファイルのチャプター情報を更新"""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # チャプターの開始時間とタイトルのマッピングを作成
    chapter_map = {chapter["start"]: chapter["title"] for chapter in chapters}

    # 全てのChapterAtomを検索して処理
    for chapter in root.findall(".//ChapterAtom"):
        time_start = chapter.find("ChapterTimeStart").text
        seconds = timestamp_to_seconds(time_start)

        # 対応する秒数が見つかった場合、タイトルを更新
        matching_title = chapter_map.get(seconds)
        if matching_title:
            chapter.find("ChapterDisplay/ChapterString").text = matching_title

    # XMLを保存
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)


def extract_chapters(mkv_path: Path, xml_path: Path) -> None:
    """MKVファイルからチャプター情報をXMLとして抽出"""
    result = subprocess.run(
        ["mkvextract", str(mkv_path), "chapters"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise Exception(f"チャプター抽出エラー: {result.stderr}")

    # 出力を一時XMLファイルに保存
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(result.stdout)


def write_chapters(mkv_path: Path, xml_path: Path) -> None:
    """XMLファイルのチャプター情報をMKVファイルに書き戻す"""
    result = subprocess.run(["mkvpropedit", str(mkv_path), "--chapters", str(xml_path)])
    if result.returncode != 0:
        raise Exception("チャプター書き込みエラー")


def find_matching_csv(mkv_path: Path) -> Optional[Path]:
    """MKVファイルに対応するCSVファイルを探す"""
    csv_path = mkv_path.with_name(f"{mkv_path.stem}_chapters.csv")
    return csv_path if csv_path.exists() else None


def process_mkv_file(mkv_path: Path) -> bool:
    """1つのMKVファイルを処理"""
    csv_path = find_matching_csv(mkv_path)
    if not csv_path:
        print(f"{mkv_path.name} に対応するCSVファイルが見つかりません")
        return False

    try:
        # 一時XMLファイルのパスを設定
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as temp_file:
            temp_xml = Path(temp_file.name)

        # チャプター抽出
        print(f"処理中: {mkv_path.name}")
        print("チャプター情報を抽出中...")
        extract_chapters(mkv_path, temp_xml)

        # チャプター更新
        print("チャプター情報を更新中...")
        chapters = read_chapters_from_csv(csv_path)
        update_xml_chapters(temp_xml, chapters)

        # チャプター書き戻し
        write_chapters(mkv_path, temp_xml)

        # 一時ファイルを削除
        temp_xml.unlink()

        # CSVファイルを削除
        csv_path.unlink()
        print(f"CSVファイルを削除しました: {csv_path.name}")

        return True

    except Exception as e:
        print(f"  エラーが発生しました: {str(e)}")
        if temp_xml.exists():
            temp_xml.unlink()
        return False


def process_directory(directory: Path) -> Tuple[int, int]:
    """ディレクトリ内のMKVファイルを再帰的に処理"""
    success_count = 0
    total_count = 0

    for mkv_path in directory.rglob("*.mkv"):
        total_count += 1
        if process_mkv_file(mkv_path):
            success_count += 1

    return success_count, total_count


def main() -> None:
    if len(sys.argv) < 2:
        print("使用方法: MKVファイルまたはフォルダをドラッグ&ドロップしてください")
        return

    total_success = 0
    total_files = 0
    skipped_files = 0

    for path in map(Path, sys.argv[1:]):
        if path.is_dir():
            print(f"\nフォルダを処理中: {path}")
            success, total = process_directory(path)
            total_success += success
            total_files += total
        elif path.suffix.lower() == ".mkv":
            csv_path = find_matching_csv(path)
            if not csv_path:
                skipped_files += 1
                continue
            total_files += 1
            if process_mkv_file(path):
                total_success += 1

    if total_files > 0:
        print(f"\n処理完了: {total_success}/{total_files} ファイルを処理しました")
        if skipped_files > 0:
            print(f"スキップ: {skipped_files} ファイル(対応するCSVファイルなし)")
    elif skipped_files > 0:
        print(
            f"\n対応するCSVファイルが見つからないため、{skipped_files} ファイルをスキップしました"
        )
    else:
        print("\nMKVファイルが見つかりませんでした")


if __name__ == "__main__":
    main()
