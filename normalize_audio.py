import shutil
import sys
import tempfile
from pathlib import Path
from typing import List

from funcs import find_video_files, normalize_audio


def wait_for_exit():
    """終了時にユーザー入力を待つ"""
    input("Enterキーを押して終了してください...")
    sys.exit(1)


def main():
    # コマンドライン引数をチェック
    if len(sys.argv) < 2:
        print("使用方法: python normalize_audio.py <入力ファイル/フォルダ...>")
        wait_for_exit()

    # 入力パスのリストを取得
    input_paths = [Path(path) for path in sys.argv[1:]]

    # 存在しないパスをチェック
    invalid_paths = [path for path in input_paths if not path.exists()]
    if invalid_paths:
        print("エラー: 以下のパスが存在しません:")
        for path in invalid_paths:
            print(f"- {path}")
        wait_for_exit()

    # すべての入力パスから動画ファイルを検索
    video_files: List[Path] = []
    for path in input_paths:
        video_files.extend(list(find_video_files(path)))

    if not video_files:
        print("動画ファイルが見つかりませんでした。")
        wait_for_exit()

    print(f"処理対象の動画ファイル数: {len(video_files)}")

    # 各動画ファイルを処理
    for i, video_file in enumerate(video_files, 1):
        print(f"処理中 [{i}/{len(video_files)}]: {video_file}")

        # 一時ファイルを作成
        with tempfile.NamedTemporaryFile(suffix=video_file.suffix, delete=False) as tmp:
            temp_file = Path(tmp.name)

        try:
            # 一時ファイルとして正規化を実行
            normalize_audio(video_file, temp_file)
            # 正規化したファイルで元のファイルを上書き
            shutil.move(temp_file, video_file, shutil.copy2)
            print(f"完了: {video_file.name}\n")
        except Exception as e:
            print(f"エラー: {video_file.name} の処理中にエラーが発生しました")
            print(f"エラー内容: {str(e)}")
            if temp_file.exists():
                temp_file.unlink()
            continue

    print("すべての処理が完了しました")
    wait_for_exit()


if __name__ == "__main__":
    main()
