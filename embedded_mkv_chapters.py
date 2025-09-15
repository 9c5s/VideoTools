# set_mkv_chapters.py
"""PotPlayerのブックマークを抽出し、対応するMKVファイルにチャプターとして直接埋め込むスクリプト."""

from __future__ import annotations

import datetime
import pathlib
import shutil
import subprocess
import sys
import time
import traceback

# --- 定数定義 ---
SCRIPT_NAME = "set_mkv_chapters.py"
MIN_BOOKMARK_PARTS = 2
MIN_ARG_COUNT = 2
# 試行するエンコーディングのリスト
ENCODINGS_TO_TRY = ["utf-8-sig", "cp932", "utf-16"]
# ブックマークのタイムスタンプを一律で調整するオフセット値 (ミリ秒単位)
# 例: -500 -> 0.5秒早める, 500 -> 0.5秒遅らせる
TIMESTAMP_OFFSET_MS = -500


def find_cli_tool(tool_name: str) -> str | None:
    """環境変数PATHから指定されたコマンドラインツールを探す。

    Args:
        tool_name: 探すツールの名前 (例: 'mkvpropedit')。

    Returns:
        ツールの実行ファイルパス。見つからない場合はNone。

    """
    path = shutil.which(tool_name)
    if not path:
        print(f"エラー: MKVToolNixの '{tool_name}' が見つかりません。")
        print("MKVToolNixをインストールし、インストールフォルダを")
        print("環境変数PATHに追加してください。")
        return None
    print(f"情報: '{tool_name}' を'{path}'に見つけました。")
    return path


def read_pbf_file(pbf_path: pathlib.Path) -> list[str] | None:
    """複数のエンコーディングを試してpbfファイルを読み込む。"""
    for encoding in ENCODINGS_TO_TRY:
        try:
            return pbf_path.read_text(encoding=encoding).splitlines()
        except (UnicodeDecodeError, OSError):  # noqa: PERF203
            continue  # 次のエンコーディングを試す

    print(f"エラー: ファイルの読み込みに失敗しました: {pbf_path}")
    print(f"試行したエンコーディング: {', '.join(ENCODINGS_TO_TRY)}")
    return None


def convert_pbf_to_chapters(pbf_path: pathlib.Path) -> pathlib.Path | None:
    """PotPlayerのブックマークをOGMチャプター形式のテキストファイルに変換する。

    Args:
        pbf_path: PotPlayerのブックマークファイルへのパス。

    Returns:
        生成されたチャプターファイルのパス。失敗した場合はNone。

    """
    output_path = pbf_path.with_suffix(f".{int(time.time())}.tmpchapters.txt")
    bookmarks: list[tuple[datetime.timedelta, str]] = []

    print(f"情報: '{pbf_path.name}' を解析しています...")
    lines = read_pbf_file(pbf_path)
    if lines is None:
        return None

    for line in lines:
        if "=" in line and "*" in line:
            line_content = line.strip().split("=", 1)[1]
            parts = line_content.split("*", 2)
            if len(parts) >= MIN_BOOKMARK_PARTS:
                try:
                    milliseconds = int(parts[0])
                    # オフセットを適用し、タイムスタンプが0未満にならないようにする
                    adjusted_ms = max(0, milliseconds + TIMESTAMP_OFFSET_MS)
                    name = parts[1].strip()
                    td = datetime.timedelta(milliseconds=adjusted_ms)
                    bookmarks.append((td, name))
                except (ValueError, IndexError):
                    continue

    if not bookmarks:
        print(f"情報: {pbf_path.name} に変換可能なブックマークがありません。")
        return None

    # --- ▼▼▼ 変更箇所 ▼▼▼ ---
    # 最初のブックマークが0秒から始まっていない場合、先頭に「ブックマーク 1」を追加
    if bookmarks[0][0].total_seconds() > 0:
        print("情報: 0秒のチャプターが存在しないため、先頭にチャプターを追加します。")
        bookmarks.insert(0, (datetime.timedelta(seconds=0), "ブックマーク 1"))
    # --- ▲▲▲ 変更箇所 ▲▲▲ ---

    with output_path.open("w", encoding="utf-8") as f:
        for i, (td, name) in enumerate(bookmarks, 1):
            total_seconds = td.total_seconds()
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            formatted_time = (
                f"{int(hours):02}:{int(minutes):02}:"
                f"{int(seconds):02}.{int(td.microseconds / 1000):03}"
            )
            f.write(f"CHAPTER{i:02}={formatted_time}\n")
            f.write(f"CHAPTER{i:02}NAME={name}\n")

    print(f"情報: 一時チャプターファイルを生成しました: {output_path.name}")
    return output_path


def set_chapters_inplace(
    mkvpropedit_path: str, mkv_path: pathlib.Path, chapter_path: pathlib.Path
) -> bool:
    """mkvpropeditを使い、既存MKVファイルにチャプターを直接書き込む。

    Args:
        mkvpropedit_path: mkvpropeditの実行ファイルパス。
        mkv_path: 対象のMKVファイルパス。
        chapter_path: チャプター情報のテキストファイルパス。

    Returns:
        処理が成功したかどうかを示す真偽値。

    """
    command = [mkvpropedit_path, str(mkv_path), "--chapters", str(chapter_path)]

    print(f"情報: '{mkv_path.name}' のチャプター情報を更新しています...")
    try:
        subprocess.run(  # noqa: S603
            command,
            shell=False,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except subprocess.CalledProcessError as e:
        print("エラー: mkvpropeditの実行に失敗しました。")
        print("--- mkvpropeditからのエラーメッセージ ---")
        print(e.stderr.strip())
        print("------------------------------------")
        return False
    else:
        print("情報: 更新に成功しました。")
        return True


def main() -> None:
    """スクリプトのメイン処理。"""
    try:
        mkvpropedit_path = find_cli_tool("mkvpropedit")
        if not mkvpropedit_path:
            return

        if len(sys.argv) < MIN_ARG_COUNT:
            print("使い方: PotPlayerのブックマークファイル (.pbf) を")
            print(f"このスクリプト ({SCRIPT_NAME}) のアイコンにD&Dしてください。")
            return

        for pbf_arg in sys.argv[1:]:
            pbf_path = pathlib.Path(pbf_arg)
            if pbf_path.suffix.lower() != ".pbf":
                print(f"スキップ: {pbf_path.name} は.pbfファイルではありません。")
                continue

            print(f"\n--- 処理開始: {pbf_path.name} ---")

            chapter_file = convert_pbf_to_chapters(pbf_path)
            if not chapter_file:
                print("--- 処理中断 ---")
                continue

            # .pbfを.mkvに置換して、対応する動画ファイルを探す
            mkv_path = pbf_path.with_suffix(".mkv")
            if not mkv_path.exists():
                print(
                    f"エラー: 対応するMKVファイルが見つかりません ({mkv_path.name})。"
                )
                print(
                    "ブックマークファイルと同じフォルダに、同じ名前のMKVファイルがあるか確認してください。"
                )
                print("情報: 一時チャプターファイルは削除されませんでした。")
                print("--- 処理中断 ---")
                continue

            if set_chapters_inplace(mkvpropedit_path, mkv_path, chapter_file):
                chapter_file.unlink()

            print("--- 処理完了 ---")

    except Exception:  # noqa: BLE001
        print("\n予期しないエラーが発生しました。")
        traceback.print_exc()


if __name__ == "__main__":
    main()
    print("\nすべての処理が完了しました。")
    input("何かキーを押すと終了します...")
