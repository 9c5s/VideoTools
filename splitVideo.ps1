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

    # 動画ファイルではない場合スキップ
    if ((ffmpeg -hide_banner -i $file.FullName 2>&1 | Select-String "Video:").Count -eq 0) {
      continue    
    }

    # 動画に対応するCSVのパスを生成
    $csvPath = Join-Path $file.DirectoryName -ChildPath "$($file.BaseName)_chapters.csv"

    # CSVが存在しない場合スキップ
    if (-Not (Test-Path -LiteralPath $csvPath)) {
      if ($file.BaseName -match '^\d{6}_') {
        continue      
      }
      Write-Output "CSVファイルが存在しません: $($file.Name)"
      continue
    }

    # CSVを読み込む
    $csvData = Import-Csv -LiteralPath $csvPath
    $rowCount = $csvData.Count

    # 行数が0の場合スキップ
    if ($rowCount -eq 0) {
      Write-Output "CSVファイルが空です: $csvPath"
      continue
    }

    Write-Output "処理開始: $($file.Name)"
    $stopwatch2 = [System.Diagnostics.Stopwatch]::StartNew()

    # 出力ファイル置き場を作成
    $outputDir = Join-Path "D:\data\VJ\tmp" -ChildPath $file.BaseName
    New-Item -Path $outputDir -ItemType Directory -Force

    $counter = 0

    # 行ごとに処理
    foreach ($row in $csvData) {

      $counter++
      $start = $row.start
      $end = $row.end
      $duration = $end - $start
      $title = $row.title

      # ファイル名に使用できない文字を全角に置換
      $invalidChars = [System.IO.Path]::GetInvalidFileNameChars()
      
      if ($title.IndexOfAny($invalidChars) -ge 0) {
        foreach ($char in $invalidChars) {
          if ($title.Contains($char)) {
            $fullWidthChar = [char]([int]$char + 65248)
            $title = $title -replace [regex]::Escape($char), $fullWidthChar
          }
        }
      }

      # 出力する動画のパスを生成
      $fileName = "$title.mp4"
      $outputPath = Join-Path $outputDir -ChildPath $fileName

      # 既に動画ファイルが存在する場合はスキップ
      if (Test-Path -LiteralPath $outputPath) {
        Write-Output "動画ファイルが既に存在します: $fileName"
        continue
      }

      Write-Output "処理開始($counter/$rowCount)"
      $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

      # 動画をチャプターごとに分割してエンコードする
      # ffmpeg -hide_banner -v error -stats -y -i $file.FullName -ss $start -t $duration -map 0:v:0 -map 0:a:0 -map_metadata -1 -c copy $outputPath
      # ffmpeg -hide_banner -v error -stats -y -ss $start -i $file.FullName -to $duration -map 0:v:0 -map 0:a:0 -map_metadata -1 -c:v h264_nvenc -preset p7 -profile:v high -b:v 0 -cq 30 -c:a aac -b:a 128k -pix_fmt yuv420p -rc-lookahead 55 -b_ref_mode each -multipass fullres -flags cgop -movflags +faststart $outputPath
      ffmpeg -hide_banner -v error -stats -y -ss $start -i $file.FullName -t $duration -map 0:v:0 -c:v libx264 -profile:v high -b:v 6000k -an -pix_fmt yuv420p -rc-lookahead 64 -flags cgop -movflags +faststart -pass 1 -f mp4 NUL
      ffmpeg -hide_banner -v error -stats -y -ss $start -i $file.FullName -t $duration -map 0:v:0 -map 0:a:0 -map_metadata -1 -c:v libx264 -profile:v high -b:v 6000k -c:a aac -b:a 128k -pix_fmt yuv420p -rc-lookahead 64 -flags cgop -movflags +faststart -pass 2 $outputPath

      Remove-Item -Path Join-Path $outputDir -ChildPath "ffmpeg2pass-0.log"
      Remove-Item -Path Join-Path $outputDir -ChildPath "ffmpeg2pass-0.log.mbtree"

      $stopwatch.Stop()
      $elapsedTime = "{0:hh\:mm\:ss\.fff}" -f $stopwatch.Elapsed
      Write-Output "処理完了($counter/$rowCount)[$elapsedTime]: $fileName`n"
    }

    $stopwatch2.Stop()
    Write-Output "処理完了[$([string]::Format("{0:hh\:mm\:ss\.fff}", $stopwatch2.Elapsed))]: $($file.Name)`n"
  }
}
