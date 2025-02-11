import sys
import subprocess
import os
import csv
import xml.etree.ElementTree as ET
import tempfile


def timestamp_to_seconds(timestamp):
    """00:00:00.000000000 形式のタイムスタンプを秒数に変換"""
    h, m, s = timestamp.split(":")
    # 小数点以下6桁で丸め
    total_seconds = float(h) * 3600 + float(m) * 60 + float(s)
    return round(total_seconds, 6)


def read_chapters_from_csv(csv_path):
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


def update_xml_chapters(xml_path, chapters):
    """XMLファイルのチャプター情報を更新"""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # チャプターの開始時間とタイトルのマッピングを作成
    chapter_map = {chapter["start"]: chapter["title"] for chapter in chapters}

    # 全てのChapterTimeStartタグを検索
    for chapter in root.findall(".//ChapterAtom"):
        time_start = chapter.find("ChapterTimeStart")
        if time_start is not None:
            seconds = timestamp_to_seconds(time_start.text)

            # ChapterStringを検索
            chapter_display = chapter.find("ChapterDisplay")
            if chapter_display is not None:
                chapter_string = chapter_display.find("ChapterString")
                if chapter_string is not None:
                    # 対応する秒数が見つかった場合、タイトルを更新
                    matching_title = chapter_map.get(seconds)
                    if matching_title:
                        chapter_string.text = matching_title

    # XMLを保存
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)


def extract_chapters(mkv_path, xml_path):
    """MKVファイルからチャプター情報をXMLとして抽出"""
    result = subprocess.run(
        ["mkvextract", mkv_path, "chapters"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise Exception(f"チャプター抽出エラー: {result.stderr}")

    # 出力を一時XMLファイルに保存
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(result.stdout)


def write_chapters(mkv_path, xml_path):
    """XMLファイルのチャプター情報をMKVファイルに書き戻す"""
    result = subprocess.run(["mkvpropedit", mkv_path, "--chapters", xml_path])
    if result.returncode != 0:
        raise Exception("チャプター書き込みエラー")


def find_matching_csv(mkv_path):
    """MKVファイルに対応するCSVファイルを探す"""
    base_path = os.path.splitext(mkv_path)[0]
    csv_path = base_path + "_chapters.csv"
    return csv_path if os.path.exists(csv_path) else None


def process_mkv_file(mkv_path):
    """1つのMKVファイルを処理"""
    csv_path = find_matching_csv(mkv_path)
    if not csv_path:
        print(f"{os.path.basename(mkv_path)} に対応するCSVファイルが見つかりません")
        return False

    try:
        # 一時XMLファイルのパスを設定
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as temp_file:
            temp_xml = temp_file.name

        # チャプター抽出
        print(f"処理中: {os.path.basename(mkv_path)}")
        print("チャプター情報を抽出中...")
        extract_chapters(mkv_path, temp_xml)

        # チャプター更新
        print("チャプター情報を更新中...")
        chapters = read_chapters_from_csv(csv_path)
        update_xml_chapters(temp_xml, chapters)

        # チャプター書き戻し
        write_chapters(mkv_path, temp_xml)

        # 一時ファイルを削除
        os.remove(temp_xml)

        return True

    except Exception as e:
        print(f"  エラーが発生しました: {str(e)}")
        if os.path.exists(temp_xml):
            os.remove(temp_xml)
        return False


def process_directory(directory):
    """ディレクトリ内のMKVファイルを再帰的に処理"""
    success_count = 0
    total_count = 0

    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(".mkv"):
                total_count += 1
                mkv_path = os.path.join(root, file)
                if process_mkv_file(mkv_path):
                    success_count += 1

    return success_count, total_count


def main():
    if len(sys.argv) < 2:
        print("使用方法: MKVファイルまたはフォルダをドラッグ&ドロップしてください")
        return

    total_success = 0
    total_files = 0
    skipped_files = 0

    for path in sys.argv[1:]:
        if os.path.isdir(path):
            print(f"\nフォルダを処理中: {path}")
            success, total = process_directory(path)
            total_success += success
            total_files += total
        elif path.lower().endswith(".mkv"):
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
