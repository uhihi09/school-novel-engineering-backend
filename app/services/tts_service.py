import base64

from app.services.gemini_service import gemini_service

# Minimal valid silent WAV — used ONLY if real TTS is unavailable (no key / API error),
# so a client media player never receives an empty payload.
_SILENT_WAV = (
    b'RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00'
    b'\x22\x56\x00\x00\x22\x56\x00\x00\x01\x00\x08\x00data\x00\x08\x00\x00'
    b'\x80' * 2000
)


class TTSService:
    def synthesize_speech(self, text: str) -> str:
        """F-6: Real text-to-speech via Gemini TTS, returned as a base64 WAV data URI.

        Falls back to a short silent clip only when real synthesis is unavailable.
        """
        audio = gemini_service.synthesize_speech_audio(text)
        if not audio:
            audio = _SILENT_WAV
        return f"data:audio/wav;base64,{base64.b64encode(audio).decode('utf-8')}"


tts_service = TTSService()
