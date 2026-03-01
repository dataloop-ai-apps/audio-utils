# Audio Utils pipeline nodes

The repository contains audio utility nodes for Dataloop pipelines.

## [Audio Utils] - Extraction

The application provides the following functions:

1. `extract_audio` - Extracts audio from a video item and creates a PromptItem:
   - Uses FFmpeg to extract the audio track as mono WAV
   - If no audio stream is found, creates a placeholder text PromptItem
   - Configuration Parameters:
     - `output_dir`: Remote directory for prompt items and audio files (default: `/audio_prompt_items`)
     - `sample_rate`: Audio sample rate in Hz (default: `16000`)
   - Output:
     - A `PromptItem` containing either the extracted audio or a placeholder message
     - Audio WAV file uploaded to `{output_dir}/audio_files/`
   - Metadata Propagation:
     - `origin_video_name`: Carried from source item's `metadata.user`
     - `time`: Carried from source item's `metadata.user`
     - `sub_videos_intervals`: Carried from source item's `metadata.user`

> **Note:** FFmpeg must be available on the runner image. The default Dataloop CPU runner images include FFmpeg.
