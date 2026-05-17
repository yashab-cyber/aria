from abc import ABC, abstractmethod

class TTSBase(ABC):
    """Abstract base class for all TTS adapters."""

    @abstractmethod
    async def generate_audio_file(self, text: str, voice_config: dict, filepath: str):
        """
        Synthesize text to an audio file.
        :param text: The text to speak.
        :param voice_config: Dictionary containing voice settings (speed, pitch, voice ID, etc.)
        :param filepath: Path where the resulting audio should be saved.
        """
        pass

    @abstractmethod
    async def speak_direct(self, text: str, voice_config: dict):
        """
        Synthesize text and play it directly through local hardware.
        :param text: The text to speak.
        :param voice_config: Dictionary containing voice settings.
        """
        pass
