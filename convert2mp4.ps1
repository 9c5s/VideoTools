# 引数のチェック
param(
    [Parameter(Mandatory=$true)]
    [string]$inputFile
)

# 文字エンコーディングをUTF-8に設定
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

try {
    # 入力ファイルのフルパスを取得
    $inputPath = [System.IO.Path]::GetFullPath($inputFile)

    # ファイルの存在確認
    if (-not (Test-Path -LiteralPath $inputPath -PathType Leaf)) {
        Write-Host "エラー: ファイルが見つかりません`nパス: $inputPath"
        exit 1
    }

    function Get-CodecInfo {
        param (
            [string]$inputPath,
            [string]$streamType  # 'v:0' または 'a:0' を指定
        )
        
        $ffprobeArgs = @(
            '-v', 'error',
            '-select_streams', $streamType,
            '-show_entries', 'stream=codec_name',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            "$inputPath"
        )
        return & ffprobe $ffprobeArgs 2>$null | Select-Object -First 1
    }

    # コーデック情報を取得
    $vcodec = Get-CodecInfo -inputPath $inputPath -streamType 'v:0'
    $acodec = Get-CodecInfo -inputPath $inputPath -streamType 'a:0'

    if (-not $vcodec) {
        Write-Host "エラー: $inputPath のビデオコーデック情報を取得できませんでした。"
        exit 1
    }

    Write-Host "検出されたコーデック - ビデオ: $vcodec, オーディオ: $(if ($null -eq $acodec) { 'なし' } else { $acodec })"

    # 出力形式を決定
    $needsEncode = $vcodec -notin @('h264', 'hevc') -or ($acodec -and $acodec -notin @('aac', 'mp3'))
    $outputPath = [System.IO.Path]::ChangeExtension($inputPath, 'mp4')
    
    # 変換実行
    Write-Host "$(if ($needsEncode) { 'エンコード' } else { 'コンテナ変換' })中: $inputPath"
    
    if ($needsEncode) {
        $ffmpegArgs = @(
            '-hide_banner',
            '-i', "$inputPath",
            '-map_metadata', '-1',
            '-c:v', 'av1_nvenc',
            '-preset', 'p7',
            '-tune', 'hq',
            '-c:a', 'aac',
            '-movflags', '+faststart',
            $outputPath
        )
    } else {
        $ffmpegArgs = @(
            '-hide_banner',
            '-i', "$inputPath",
            '-map_metadata', '-1',
            '-c', 'copy',
            '-movflags', '+faststart',
            $outputPath
        )
    }
    
    $process = Start-Process ffmpeg -ArgumentList $ffmpegArgs -NoNewWindow -PassThru -Wait
    
    if ($process.ExitCode -eq 0) {
        Write-Host "変換成功: $inputPath"
    } else {
        Write-Host "エラー: 変換に失敗しました: $inputPath"
        exit 1
    }
}
catch {
    Write-Host "エラー: 処理中に問題が発生しました: $_"
    exit 1
} 