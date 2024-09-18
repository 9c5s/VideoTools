param (
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$InputFiles
)

# 入力ファイルが指定されていない場合の処理
if (-not $InputFiles -or $InputFiles.Count -eq 0) {
  Write-Host "エラー: 結合する動画ファイルをドラッグ＆ドロップしてください。" -ForegroundColor Red
  exit 1
}

# Windowsの自然順ソートを使用するためのクラスを定義
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Collections;

public class NaturalStringComparer : IComparer
{
    [DllImport("shlwapi.dll", CharSet = CharSet.Unicode)]
    public static extern int StrCmpLogicalW(string psz1, string psz2);

    public int Compare(object x, object y)
    {
        return StrCmpLogicalW(x as string, y as string);
    }
}
"@

# 自然順ソートでファイルリストをソート
$comparer = New-Object NaturalStringComparer
$sortedFiles = New-Object System.Collections.ArrayList
[void]$sortedFiles.AddRange($InputFiles)
$sortedFiles.Sort($comparer)

# 出力ファイル名を生成
function Get-SafeFileName($fileName) {
  $invalidChars = [System.IO.Path]::GetInvalidFileNameChars()
  return -join ($fileName -split '' | Where-Object { $_ -notin $invalidChars })
}

$firstFileName = [System.IO.Path]::GetFileNameWithoutExtension($sortedFiles[0])
$lastFileName = [System.IO.Path]::GetFileNameWithoutExtension($sortedFiles[$sortedFiles.Count - 1])
$firstFileName = Get-SafeFileName $firstFileName
$lastFileName = Get-SafeFileName $lastFileName
$outputFileName = "$firstFileName~$lastFileName.mp4"

# 出力先ディレクトリを設定（最初のファイルのディレクトリ）
$outputDirectory = [System.IO.Path]::GetDirectoryName($sortedFiles[0])
$outputFilePath = [System.IO.Path]::Combine($outputDirectory, $outputFileName)

# 一時的なリストファイルを作成
$tempListPath = [System.IO.Path]::GetTempFileName()
$tempListPath = [System.IO.Path]::ChangeExtension($tempListPath, ".txt")

try {
  # リストファイルにファイルパスを書き込む
  $listContent = foreach ($file in $sortedFiles) {
    $escapedPath = $file.Replace("'", "'\''")
    "file '$escapedPath'"
  }
  Set-Content -Path $tempListPath -Value $listContent -Encoding UTF8

  # ffmpegを実行
  $ffmpegArgs = @(
    '-hide_banner',
    '-v', 'error',
    '-stats',
    '-y',
    '-f', 'concat',
    '-safe', '0',
    '-i', $tempListPath,
    '-c', 'copy',
    '-map', '0:v',
    '-map', '0:a',
    $outputFilePath
  )
  ffmpeg @ffmpegArgs

}
finally {
  # 一時ファイルを削除
  if (Test-Path $tempListPath) {
    Remove-Item $tempListPath -Force
  }
}
