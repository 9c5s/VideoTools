[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

if ($Args.Count -eq 0) {
  Write-Output "このスクリプトに動画ファイルをD&Dしてください"
  Read-Host -Prompt "Enterキーを押して終了します"
  exit 1
}

$Args | ForEach-Object {

  $files = @()

  # 入力アイテムを取得
  $item = Get-Item -LiteralPath $_

  # フォルダの場合は再帰的にファイルを取得して配列に追加
  if ($item.PSIsContainer) {
    $files += Get-ChildItem -LiteralPath $_ -Recurse -File
  }
  else {
    # ファイルの場合はそのまま配列に追加
    $files += $item
  }

  # 配列のファイルを処理
  foreach ($file in $files) {
    
    # 出力するCSVのパスを生成
    $csvPath = Join-Path $file.DirectoryName "$($file.BaseName)_chapters.csv"

    # 既にCSVファイルが存在する場合はスキップ
    if (Test-Path -LiteralPath $csvPath) {
      Write-Output "CSVファイルが既に存在します: $csvPath"
      continue
    }

    # 項目行のみのCSVファイルを作成
    "id,start,end,title" | Out-File -LiteralPath $csvPath

    # ffprobeとjqを組み合わせてデータ行を生成して項目行の後に追記
    ffprobe -hide_banner -v error -i $file.FullName -show_chapters -of json | jq -r '.chapters[] | [(.id|tostring), .start_time, .end_time, ("\"" + .tags.title + "\"")] | join(",")' | Out-File -LiteralPath $csvPath -Append

    Write-Output "CSVファイルが作成されました: $csvPath"
  }
}
