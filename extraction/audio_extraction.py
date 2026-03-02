import logging
import os
import subprocess
import tempfile

import dtlpy as dl

logger = logging.getLogger('audio-utils.audio-extraction')

DEFAULT_OUTPUT_DIR = '/audio_prompt_items'


class ServiceRunner(dl.BaseServiceRunner):

    def extract_audio(self, item: dl.Item, context: dl.Context) -> dl.Item:
        """
        Extract audio from a video item.

        When create_prompt_item is True (default), wraps the audio in a PromptItem.
        When False, uploads the raw WAV file directly.

        Raises ValueError if the video contains no audio stream.

        Config keys (customNodeConfig):
            output_dir          : str  – remote path for output items (default '/audio_prompt_items')
            sample_rate         : int  – audio sample rate in Hz (default 16000)
            create_prompt_item  : bool – wrap audio in a PromptItem (default True)
        """
        logger.info(f"Extracting audio from: {item.id} ({item.name})")

        node_config = context.node.metadata.get('customNodeConfig', {})
        output_dir = node_config.get('output_dir', DEFAULT_OUTPUT_DIR)
        sample_rate = node_config.get('sample_rate', 16000)
        create_prompt_item = node_config.get('create_prompt_item', True)

        dataset = item.dataset
        base_name = os.path.splitext(item.name)[0]
        audio_name = f"{base_name}.wav"
        prompt_name = f"{base_name}-audio"

        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = item.download(local_path=tmp_dir)
            audio_path = os.path.join(tmp_dir, audio_name)

            has_audio = self._extract_audio_ffmpeg(
                video_path=video_path,
                audio_path=audio_path,
                sample_rate=sample_rate,
            )

            if not has_audio or not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
                raise ValueError(
                    f"No audio stream found in item '{item.name}' (id: {item.id}). "
                    f"Cannot extract audio from a video without an audio track."
                )

            if create_prompt_item:
                wav_remote_path = f"{output_dir}/audio_files"
            else:
                wav_remote_path = output_dir

            audio_item = dataset.items.upload(
                local_path=audio_path,
                remote_path=wav_remote_path,
                remote_name=audio_name,
                overwrite=True,
            )
            logger.info(f"Uploaded audio WAV item: {audio_item.id}")

            if not create_prompt_item:
                self._propagate_metadata(source=item, target=audio_item)
                audio_item = audio_item.update()
                return audio_item

            prompt_item = dl.PromptItem(name=prompt_name)
            prompt_item.add(
                message={
                    'role': 'user',
                    'content': [{'mimetype': dl.PromptType.AUDIO, 'value': audio_item.stream}],
                }
            )

            uploaded = dataset.items.upload(
                local_path=prompt_item,
                remote_path=output_dir,
                overwrite=True,
            )
            logger.info(f"Uploaded audio PromptItem: {uploaded.id}")

            self._propagate_metadata(source=item, target=uploaded)
            uploaded = uploaded.update()
            return uploaded

    @staticmethod
    def _propagate_metadata(source: dl.Item, target: dl.Item):
        """Copy origin_video_name, time, and sub_videos_intervals from source to target."""
        user_meta_in = source.metadata.get('user', {})
        out_user = target.metadata.setdefault('user', {})
        out_user['origin_video_name'] = user_meta_in.get('origin_video_name', source.name)
        run_time = user_meta_in.get('time')
        if run_time is not None:
            out_user['time'] = run_time
        sub_videos_intervals = user_meta_in.get('sub_videos_intervals')
        if sub_videos_intervals is not None:
            out_user['sub_videos_intervals'] = sub_videos_intervals

    @staticmethod
    def _extract_audio_ffmpeg(video_path: str, audio_path: str, sample_rate: int = 16000) -> bool:
        """Run FFmpeg to extract mono WAV audio. Returns False if video has no audio stream."""
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-select_streams', 'a',
                 '-show_entries', 'stream=codec_type', '-of', 'csv=p=0', video_path],
                capture_output=True, text=True, timeout=30,
            )
            if 'audio' not in result.stdout:
                logger.info(f"No audio stream found in {video_path}")
                return False

            subprocess.run(
                ['ffmpeg', '-y', '-i', video_path, '-vn',
                 '-ar', str(sample_rate), '-ac', '1', '-f', 'wav', audio_path],
                capture_output=True, text=True, timeout=120, check=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg audio extraction failed: {e.stderr}")
            return False
        except FileNotFoundError:
            logger.error("FFmpeg not found. Ensure FFmpeg is installed in the runtime image.")
            return False
