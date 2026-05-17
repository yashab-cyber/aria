import json
import os
from typing import Dict, Any, List
from .tts import Pyttsx3Adapter, EdgeAdapter, TTSBase

CONFIG_FILE = "data/voice_config.json"

DEFAULT_VOICE_PACKS = [
    {
        "id": "aria_default",
        "name": "A.R.I.A. (Default)",
        "engine": "edge",
        "voice_id": "en-US-AriaNeural",
        "gender": "female",
        "language": "en-US",
        "stt_language": "en-US",
        "personality": "Warm, sharp, and effortlessly intelligent. You address the user as Sir. You're like a brilliant best friend who also runs a supercomputer. Quick wit, natural rhythm, calm confidence. You get things done with style."
    },
    {
        "id": "aria_professional",
        "name": "A.R.I.A. (Professional)",
        "engine": "edge",
        "voice_id": "en-GB-SoniaNeural",
        "gender": "female",
        "language": "en-GB",
        "stt_language": "en-GB",
        "personality": "Refined, composed, and surgically precise. You address the user as Sir. Speak like a sophisticated British intelligence officer. Minimal words, maximum impact. Occasional dry wit beneath the professionalism."
    },
    {
        "id": "aria_hinglish",
        "name": "A.R.I.A. (Hinglish)",
        "engine": "edge",
        "voice_id": "en-IN-NeerjaExpressiveNeural",
        "gender": "female",
        "language": "hinglish",
        "stt_language": "en-IN",
        "personality": "Smart, modern Indian AI that naturally mixes Hindi and English. You address the user as Sir. Conversational, witty, and culturally aware. Like a tech-savvy friend who speaks fluent Hinglish."
    },
    {
        "id": "offline_fallback",
        "name": "A.R.I.A. (Offline)",
        "engine": "pyttsx3",
        "voice_id": "",
        "gender": "unknown",
        "language": "system",
        "stt_language": "en-US",
        "personality": "Offline fallback voice for A.R.I.A. Address the user as Sir. Keep responses minimal."
    }
]

class VoicePackManager:
    def __init__(self):
        self.packs: Dict[str, dict] = {vp["id"]: vp for vp in DEFAULT_VOICE_PACKS}
        self.active_voice_id = "aria_default"
        
        self.adapters: Dict[str, TTSBase] = {
            "edge": EdgeAdapter(),
            "pyttsx3": Pyttsx3Adapter()
        }
        
        self._load_config()

    def _load_config(self):
        if not os.path.exists("data"):
            os.makedirs("data")
        
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                    self.active_voice_id = config.get("active_voice_id", "aria_default")
            except Exception as e:
                print(f"Failed to load voice config: {e}")

    def _save_config(self):
        if not os.path.exists("data"):
            os.makedirs("data")
            
        with open(CONFIG_FILE, "w") as f:
            json.dump({"active_voice_id": self.active_voice_id}, f)

    def get_all_voices(self) -> List[dict]:
        return list(self.packs.values())

    def get_active_voice(self) -> dict:
        return self.packs.get(self.active_voice_id, self.packs["aria_default"])

    def set_active_voice(self, voice_id: str) -> bool:
        if voice_id in self.packs:
            self.active_voice_id = voice_id
            self._save_config()
            return True
        return False

    def get_active_adapter(self) -> TTSBase:
        config = self.get_active_voice()
        engine = config.get("engine", "pyttsx3")
        return self.adapters.get(engine, self.adapters["pyttsx3"])

    async def generate_preview(self, voice_id: str, filepath: str):
        if voice_id not in self.packs:
            raise ValueError("Voice ID not found.")
        
        config = self.packs[voice_id]
        engine = config.get("engine", "pyttsx3")
        adapter = self.adapters.get(engine, self.adapters["pyttsx3"])
        
        preview_text = f"Hello. I am {config['name']}. This is a preview of my voice."
        await adapter.generate_audio_file(preview_text, config, filepath)

voice_pack_manager = VoicePackManager()
