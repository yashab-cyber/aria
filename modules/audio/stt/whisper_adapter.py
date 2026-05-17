import os
import aiohttp
import asyncio
from .stt_base import STTBase
import speech_recognition as sr
import tempfile
from config import config

class WhisperSTTAdapter(STTBase):
    """High-fidelity STT using OpenAI Whisper API."""
    
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.api_key = config.openai_api_key
        self.api_url = "https://api.openai.com/v1/audio/transcriptions"

    async def _call_whisper_api(self, file_path: str, language: str = "en") -> str:
        if not self.api_key:
            return "Error: OPENAI_API_KEY is not set."
            
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()

            import aiohttp
            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field('file', file_data, filename=os.path.basename(file_path), content_type='audio/mpeg')
                data.add_field('model', 'whisper-1')
                # Map language like "en-US" to "en" for Whisper
                data.add_field('language', language.split('-')[0] if '-' in language else language)

                headers = {'Authorization': f'Bearer {self.api_key}'}

                async with session.post(self.api_url, data=data, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get('text', '')
                    else:
                        error_text = await response.text()
                        return f"Whisper API error: {response.status} - {error_text}"
        except Exception as e:
            return f"Error connecting to Whisper API: {e}"

    async def transcribe_audio_file(self, file_path: str, language: str = "en-US") -> str:
        return await self._call_whisper_api(file_path, language)

    async def transcribe_microphone(self, timeout: int = 5, phrase_time_limit: int = 10, language: str = "en-US") -> str:
        # We need to record audio via mic, save to a temp file, then send to Whisper.
        loop = asyncio.get_event_loop()
        wav_path = await loop.run_in_executor(None, self._record_to_temp_sync, timeout, phrase_time_limit)
        
        if not wav_path:
            return "" # Timeout or no audio
            
        try:
            result = await self._call_whisper_api(wav_path, language)
            return result
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)
        
    def _record_to_temp_sync(self, timeout: int, phrase_time_limit: int) -> str:
        with sr.Microphone() as source:
            print("Listening (Whisper STT)...")
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_wav:
                    temp_wav.write(audio.get_wav_data())
                    return temp_wav.name
            except sr.WaitTimeoutError:
                return ""
