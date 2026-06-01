import os
import asyncio
from core.tool_registry import aria_tool
from config import config
from core.state import state_manager

class VoiceAgent:
    def __init__(self):
        self._listening_continuously = False
        self._continuous_task = None
        self._speak_lock = asyncio.Lock()
        self._get_stt_adapter() # warm up

    def _get_stt_adapter(self):
        from modules.audio.stt.google_adapter import GoogleSTTAdapter
        from modules.audio.stt.whisper_adapter import WhisperSTTAdapter
        if config.openai_api_key:
            return WhisperSTTAdapter()
        return GoogleSTTAdapter()

    @aria_tool(name="speak", description="Synthesizes text into spoken audio.")
    async def speak(self, text: str) -> str:
        async with self._speak_lock:
            await state_manager.set_state("speaking")
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
            finally:
                await state_manager.set_state("idle")

    async def generate_speech_audio(self, text: str) -> bytes:
        """Synthesizes text and returns the raw audio bytes."""
        async with self._speak_lock:
            from modules.audio.voice_pack_manager import voice_pack_manager
            import tempfile
            import os

            adapter = voice_pack_manager.get_active_adapter()
            voice_config = voice_pack_manager.get_active_voice()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
                temp_path = temp_audio.name
            try:
                await adapter.generate_audio_file(text, voice_config, temp_path)
                with open(temp_path, "rb") as f:
                    audio_bytes = f.read()
                return audio_bytes
            except Exception as e:
                print(f"[generate_speech_audio] Error: {e}")
                return b""
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

    @aria_tool(name="listen", description="Activates microphone, listens to the user for a single phrase, and transcribes audio to text.")
    async def listen(self, language: str = "en-US") -> str:
        try:
            stt = self._get_stt_adapter()
            transcription = await stt.transcribe_microphone(language=language)
            return transcription if transcription else "No speech detected."
        except Exception as e:
            return f"Error listening: {str(e)}"

    @aria_tool(name="transcribe_audio_file", description="Reads an audio file (.wav, .mp3) and transcribes the speech to text.")
    async def transcribe_audio_file(self, file_path: str, language: str = "en-US") -> str:
        if not os.path.exists(file_path):
            return f"File not found: {file_path}"
        try:
            stt = self._get_stt_adapter()
            return await stt.transcribe_audio_file(file_path, language=language)
        except Exception as e:
            return f"Error transcribing file: {str(e)}"

    @aria_tool(name="translate_audio_file", description="Reads an audio file, transcribes it, and translates the text to English.")
    async def translate_audio_file(self, file_path: str) -> str:
        transcript = await self.transcribe_audio_file(file_path)
        if transcript.startswith("Error") or transcript.startswith("File not found"):
            return transcript
            
        # Use LLM to translate
        from litellm import acompletion
        try:
            response = await acompletion(
                model=config.aria_model,
                messages=[{"role": "user", "content": f"Translate this text to English exactly, without adding commentary: {transcript}"}],
                api_base=config.api_base
            )
            return f"Original Transcript: {transcript}\n\nEnglish Translation: {response.choices[0].message.content}"
        except Exception as e:
            return f"Error translating transcript: {str(e)}"

    @aria_tool(name="start_continuous_listening", description="Starts listening in the background for a wake word (e.g. 'Aria') to interact proactively.")
    async def start_continuous_listening(self) -> str:
        if self._listening_continuously:
            return "Already listening in the background."
            
        self._listening_continuously = True
        
        async def _background_listen_loop():
            stt = self._get_stt_adapter()
            print("[VoiceAgent] Background listening started...")
            while self._listening_continuously:
                text = await stt.transcribe_microphone(timeout=3, phrase_time_limit=5)
                if text and ("aria" in text.lower() or "arya" in text.lower()):
                    print(f"[VoiceAgent] Wake word detected in: '{text}'")
                    # Here we would inject into the orchestrator. For now, it just prints.
                    # from core.aria import orchestrator
                    # ... processing logic
                await asyncio.sleep(0.5)
                
        self._continuous_task = asyncio.create_task(_background_listen_loop())
        return "Continuous listening started. A.R.I.A is now listening for the wake word."

    @aria_tool(name="stop_continuous_listening", description="Stops the continuous listening background task.")
    async def stop_continuous_listening(self) -> str:
        if not self._listening_continuously:
            return "Not currently listening continuously."
            
        self._listening_continuously = False
        if self._continuous_task:
            self._continuous_task.cancel()
            self._continuous_task = None
        return "Continuous listening stopped."

voice_agent = VoiceAgent()
