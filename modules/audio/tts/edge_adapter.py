import asyncio
import re
import edge_tts
from .tts_base import TTSBase
import os
from pydub import AudioSegment
from pydub.playback import play


def _clean_for_speech(text: str) -> str:
    """Strip markdown, code blocks, and special chars that make TTS stutter."""
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', ' code block omitted ', text)
    # Remove inline code
    text = re.sub(r'`[^`]+`', '', text)
    # Remove markdown formatting
    text = re.sub(r'[*_~#>\[\]()!]', '', text)
    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


class EdgeAdapter(TTSBase):
    def __init__(self):
        pass

    async def generate_audio_file(self, text: str, voice_config: dict, filepath: str):
        voice = voice_config.get("voice_id", "en-US-AriaNeural")

        # Clean the text so TTS doesn't read markdown or URLs
        clean = _clean_for_speech(text)
        if not clean:
            clean = "Done."

        communicate = edge_tts.Communicate(clean, voice)
        await communicate.save(filepath)

    async def speak_direct(self, text: str, voice_config: dict):
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
            temp_path = temp_audio.name

        await self.generate_audio_file(text, voice_config, temp_path)

        try:
            audio = AudioSegment.from_file(temp_path)
            play(audio)
        except Exception as e:
            print(f"Error playing local audio: {e}")
        finally:
            try:
                os.remove(temp_path)
            except:
                pass
