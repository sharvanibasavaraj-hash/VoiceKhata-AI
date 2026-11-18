import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Gnani API configuration
GNANI_API_KEY = os.getenv("GNANI_API_KEY", "").strip()

STT_URL = "https://api.vachana.ai/stt/v3"
TTS_URL = "https://api.vachana.ai/api/v1/tts/inference"

STT_MODEL = "prisma-v3.0"
TTS_MODEL = "timbre-v3.0"

# Frontend language values mapped to Gnani language codes
LANGUAGE_CODES = {
    "en": "en-IN",
    "kn": "kn-IN",
    "hi": "hi-IN"
}

# Default TTS voice; can be changed after testing the voice catalog.
TTS_VOICE = os.getenv("GNANI_TTS_VOICE", "Chetana")

MAX_AUDIO_SIZE = 15 * 1024 * 1024  # 15 MB
REQUEST_TIMEOUT = 60


def get_language_code(language):
    return LANGUAGE_CODES.get(language, "en-IN")


def get_api_key():
    if not GNANI_API_KEY:
        raise ValueError(
            "Gnani API key is missing. Add GNANI_API_KEY to your .env file."
        )

    return GNANI_API_KEY