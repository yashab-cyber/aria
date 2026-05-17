import speech_recognition as sr
import asyncio
from .stt_base import STTBase

class GoogleSTTAdapter(STTBase):
    """Fallback STT using Google Web Speech API."""
    
    def __init__(self):
        self.recognizer = sr.Recognizer()

    async def transcribe_audio_file(self, file_path: str, language: str = "en-US") -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._transcribe_file_sync, file_path, language)
        
    def _transcribe_file_sync(self, file_path: str, language: str) -> str:
        with sr.AudioFile(file_path) as source:
            audio_data = self.recognizer.record(source)
            try:
                return self.recognizer.recognize_google(audio_data, language=language)
            except sr.UnknownValueError:
                return "Could not understand audio."
            except sr.RequestError as e:
                return f"Google API error: {e}"

    async def transcribe_microphone(self, timeout: int = 5, phrase_time_limit: int = 10, language: str = "en-US") -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._transcribe_mic_sync, timeout, phrase_time_limit, language)
        
    def _transcribe_mic_sync(self, timeout: int, phrase_time_limit: int, language: str) -> str:
        with sr.Microphone() as source:
            print("Listening (Google STT)...")
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
                return self.recognizer.recognize_google(audio, language=language)
            except sr.WaitTimeoutError:
                return "" # Silent return on timeout
            except sr.UnknownValueError:
                return "Could not understand audio."
            except sr.RequestError as e:
                return f"Google API error: {e}"
