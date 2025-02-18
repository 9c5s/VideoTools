from pathlib import Path

from ffmpeg_normalize import FFmpegNormalize


def normalize_audio(input_file: Path, output_file: Path) -> None:
    """音量を正規化"""
    normalizer = FFmpegNormalize(
        normalization_type="ebu",
        target_level=-5,
        print_stats=False,
        loudness_range_target=7,
        keep_loudness_range_target=True,
        keep_lra_above_loudness_range_target=False,
        true_peak=0,
        offset=0,
        lower_only=False,
        auto_lower_loudness_target=True,
        dual_mono=False,
        dynamic=False,
        audio_codec="aac",
        audio_bitrate=128000,
        sample_rate=None,
        audio_channels=None,
        keep_original_audio=False,
        pre_filter=None,
        post_filter=None,
        video_codec="copy",
        video_disable=False,
        subtitle_disable=True,
        metadata_disable=True,
        chapters_disable=True,
        extra_input_options=None,
        extra_output_options=["-movflags", "faststart"],
        output_format=None,
        dry_run=False,
        debug=False,
        progress=False,
    )
    normalizer.add_media_file(str(input_file), str(output_file))
    normalizer.run_normalization()
