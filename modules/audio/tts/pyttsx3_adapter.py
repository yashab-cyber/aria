import pyttsx3
import asyncio
from .tts_base import TTSBase

class Pyttsx3Adapter(TTSBase):
    def __init__(self):
        self.engine = None

    def _init_engine(self, voice_config: dict):
        if self.engine is None:
            self.engine = pyttsx3.init()
        
        # Apply voice settings if provided (pyttsx3 is limited, but we can try)
        speed = voice_config.get("speed", 1.0)
        self.engine.setProperty('rate', int(200 * speed))

        # Some systems support setting voice by ID
        vid = voice_config.get("voice_id")
        if vid:
            voices = self.engine.getProperty('voices')
            for v in voices:
                if vid.lower() in v.id.lower() or vid.lower() in v.name.lower():
                    self.engine.setProperty('voice', v.id)
                    break

    async def generate_audio_file(self, text: str, voice_config: dict, filepath: str):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._generate_sync, text, voice_config, filepath)

    def _generate_sync(self, text: str, voice_config: dict, filepath: str):
        self._init_engine(voice_config)
        self.engine.save_to_file(text, filepath)
        self.engine.runAndWait()

    async def speak_direct(self, text: str, voice_config: dict):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._speak_sync, text, voice_config)

    def _speak_sync(self, text: str, voice_config: dict):
        self._init_engine(voice_config)
        self.engine.say(text)
        self.engine.runAndWait()
