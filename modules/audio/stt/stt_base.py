from abc import ABC, abstractmethod

class STTBase(ABC):
    """Base class for Speech-to-Text adapters."""
    
    @abstractmethod
    async def transcribe_audio_file(self, file_path: str, language: str = "en-US") -> str:
        """Transcribe an audio file from a path."""
        pass
        
    @abstractmethod
    async def transcribe_microphone(self, timeout: int = 5, phrase_time_limit: int = 10) -> str:
        """Transcribe directly from the microphone."""
        pass
