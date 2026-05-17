import os
import pyttsx3
import speech_recognition as sr
import asyncio
from core.tool_registry import aria_tool

class VoiceAgent:
    def __init__(self):
        self.engine = None

    @aria_tool(name="speak", description="Synthesizes text into spoken audio.")
    async def speak(self, text: str) -> str:
        try:
            from modules.audio.audio_manager import audio_manager
            from modules.audio.voice_pack_manager import voice_pack_manager
            import tempfile
            import os

            adapter = voice_pack_manager.get_active_adapter()
            voice_config = voice_pack_manager.get_active_voice()
            
            if audio_manager.mode == "browser_audio":
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
                    temp_path = temp_audio.name
                
                await adapter.generate_audio_file(text, voice_config, temp_path)
                
                with open(temp_path, "rb") as f:
                    audio_bytes = f.read()
                
                os.remove(temp_path)
                await audio_manager.send_to_browser(audio_bytes)
                return "Spoke successfully to browser."
            else:
                # Direct hardware speaker
                await adapter.speak_direct(text, voice_config)
                return "Spoke successfully via hardware."
                
        except Exception as e:
            return f"Error speaking: {str(e)}"

    @aria_tool(name="listen", description="Activates microphone, listens to the user, and transcribes audio to text.")
    async def listen(self) -> str:
        try:
            loop = asyncio.get_event_loop()
            transcription = await loop.run_in_executor(None, self._listen_sync)
            return transcription
        except Exception as e:
            return f"Error listening: {str(e)}"

    def _listen_sync(self) -> str:
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            print("Listening...")
            # Adjust for ambient noise briefly
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            # Listen for up to 5 seconds of audio
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
        
        try:
            # Using Google Web Speech API for simplicity (requires internet)
            text = recognizer.recognize_google(audio)
            return text
        except sr.UnknownValueError:
            return "Could not understand audio"
        except sr.RequestError as e:
            return f"Could not request results; {e}"

voice_agent = VoiceAgent()
