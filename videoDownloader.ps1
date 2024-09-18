param(
  [string]$URL = ""
)
$outputTemplate = "%(title)s_%(height)s_%(fps)s_%(vcodec.:4)s_(%(id)s).%(ext)s"
$listFileName = "downloaded_videos.txt"

$tmpDir = Join-Path $env:TEMP -ChildPath "yt-dlp"
if (-Not (Test-Path -Path $tmpDir)) {
  New-Item -Path $tmpDir -ItemType Directory
}

$tmpPath = Join-Path $tmpDir -ChildPath $outputTemplate

yt-dlp -N 16 --download-archive $listFileName -S "codec:avc:aac,res:1080,fps:60,hdr:sdr" -f "bv+ba" -o $tmpPath $URL

$files = Get-ChildItem -Path $tmpDir
$totalCount = $files.Count
$currentCount = 0

foreach ($file in $files) {

  $currentCount++

  Write-Output "`n処理開始($currentCount/$totalCount)"
  $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

  # 無音部分を検出
  $silenceDetectOutput = ffmpeg -v warning -i $file -vn -map 0:a:0 -c:a pcm_s16le -f wav - | ffmpeg -hide_banner -i - -af "silencedetect=noise=-50dB:d=0.5" -f null - 2>&1

  # 無音部分の開始と終了時間を抽出
  $silenceRanges = $silenceDetectOutput | Select-String -Pattern "silence_(start|end)" | ForEach-Object {
    if ($_ -match ".*silence_(start|end): (\d+(\.\d+)?).*") {
      $matches[2]
    }
  }

  # 無音区間が存在しない場合
  if ($silenceRanges.Count -eq 0) {
    # カットしない
    ffmpeg -v warning -y -i $file.FullName -c copy $file.Name
  }

  # 無音区間が1つのみの場合
  if ($silenceRanges.Count -eq 2) {
    $startTime = [double]$silenceRanges[0]
    $endTime = [double]$silenceRanges[1]

    if ($startTime -eq 0) {
      # 先頭の無音部分をカット
      $ssTo = "-ss $endTime"
    }
    elseif ($endTime -eq 0) {
      # ？？？
    }
    else {
      # 最後の無音部分をカット
      $ssTo = "-ss $startTime -to $endTime"
    }
  }

  # 無音区間が2つ以上の場合
  if ($silenceRanges.Count -ge 4) {
    # 先頭の無音の終了時間と末尾の無音の開始時間
    $startTime = [double]$silenceRanges[1]
    $endTime = [double]$silenceRanges[-2]

    $ssTo = "-ss $startTime -to $endTime"
  }

  Invoke-Expression "ffmpeg -hide_banner -v error -stats -y -i ""$($file.FullName)"" $ssTo -map_metadata -1 -c:v h264_nvenc -profile:v high -cq 30 -maxrate 6000k -bufsize 12000k -c:a copy -pix_fmt yuv420p -flags cgop -movflags +faststart ""$($file.Name)"""

  # Invoke-Expression "ffmpeg -hide_banner -v error -stats -y -i ""$($file.FullName)"" $ssTo -map 0:v:0 -c:v libx264 -profile:v high -b:v 6000k -an -pix_fmt yuv420p -rc-lookahead 64 -flags cgop -movflags +faststart -pass 1 -f mp4 NUL"
  # Invoke-Expression "ffmpeg -hide_banner -v error -stats -y -i ""$($file.FullName)"" $ssTo -map 0:v:0 -map 0:a:0 -map_metadata -1 -c:v libx264 -profile:v high -b:v 6000k -c:a aac -b:a 128k -pix_fmt yuv420p -rc-lookahead 64 -flags cgop -movflags +faststart -pass 2 ""$($file.Name)"""

  # Remove-Item -Path "ffmpeg2pass-0.log"
  # Remove-Item -Path "ffmpeg2pass-0.log.mbtree"

  $stopwatch.Stop()
  Write-Output "処理完了($currentCount/$totalCount)[$([string]::Format("{0:hh\:mm\:ss\.fff}", $stopwatch.Elapsed))]: $($file.Name)"

}

Remove-Item -Path $tmpDir -Recurse
