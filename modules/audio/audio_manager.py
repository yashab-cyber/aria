import os
import tempfile
from pydub import AudioSegment
import speech_recognition as sr
from typing import Optional, Callable
import asyncio

class AudioManager:
    def __init__(self):
        # Options: "browser_audio" or "raspberrypi_audio"
        self.mode = "browser_audio"
        self.browser_audio_callback: Optional[Callable] = None

    def set_mode(self, mode: str):
        if mode in ["browser_audio", "raspberrypi_audio"]:
            self.mode = mode
            print(f"[AudioManager] Mode set to: {mode}")

    def register_browser_audio_callback(self, callback: Callable):
        """Register a callback to send audio bytes to the browser."""
        self.browser_audio_callback = callback

    async def send_to_browser(self, audio_bytes: bytes):
        """Send audio to the browser via the registered callback."""
        if self.browser_audio_callback:
            if asyncio.iscoroutinefunction(self.browser_audio_callback):
                await self.browser_audio_callback(audio_bytes)
            else:
                self.browser_audio_callback(audio_bytes)

    def process_webm_to_text(self, webm_bytes: bytes, language: str = "en-US") -> str:
        """Convert incoming WebM audio from browser to WAV and transcribe it."""
        try:
            # Save bytes to a temporary webm file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_webm:
                temp_webm.write(webm_bytes)
                temp_webm_path = temp_webm.name

            # Convert to WAV using pydub
            wav_path = temp_webm_path.replace(".webm", ".wav")
            audio = AudioSegment.from_file(temp_webm_path, format="webm")
            audio.export(wav_path, format="wav")

            # Transcribe
            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_path) as source:
                audio_data = recognizer.record(source)
                try:
                    text = recognizer.recognize_google(audio_data, language=language)
                except sr.UnknownValueError:
                    text = "Could not understand audio"
                except sr.RequestError as e:
                    text = f"Speech recognition request failed: {e}"

            # Cleanup
            os.remove(temp_webm_path)
            os.remove(wav_path)

            return text

        except Exception as e:
            print(f"[AudioManager] Error processing audio: {e}")
            return f"Error processing audio: {str(e)}"

audio_manager = AudioManager()
