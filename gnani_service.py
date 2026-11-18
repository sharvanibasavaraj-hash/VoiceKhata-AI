import requests

from config import (
    STT_URL,
    TTS_URL,
    STT_MODEL,
    TTS_MODEL,
    TTS_VOICE,
    REQUEST_TIMEOUT,
    get_api_key
)


def transcribe_audio(audio_bytes, filename, language_code):
    """
    Send recorded audio to Gnani Speech-to-Text.
    Returns the recognised transcript.
    """

    api_key = get_api_key()

    headers = {
        "X-API-Key-ID": api_key
    }

    files = {
        "audio_file": (
            filename,
            audio_bytes,
            "application/octet-stream"
        )
    }

    data = {
        "model": STT_MODEL,
        "language_code": language_code,
        "format": "transcribe"
    }

    try:
        response = requests.post(
            STT_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=REQUEST_TIMEOUT
        )

        if not response.ok:
            raise RuntimeError(
                f"Gnani STT error ({response.status_code}): "
                f"{response.text[:1000]}"
            )

        result = response.json()

        transcript = result.get("transcript", "").strip()

        if not transcript:
            raise RuntimeError(
                "Gnani could not recognise any speech in the recording."
            )

        return transcript

    except requests.RequestException as error:
        raise RuntimeError(
            f"Could not connect to Gnani STT: {error}"
        ) from error


def synthesize_speech(text, language_code):
    """
    Convert the assistant's text response into audio using Gnani TTS.
    Returns raw WAV audio bytes.
    """

    api_key = get_api_key()

    headers = {
        "X-API-Key-ID": api_key,
        "Content-Type": "application/json"
    }

    payload = {
        "text": text,
        "model": TTS_MODEL,
        "voice": TTS_VOICE,
        "language": language_code,
        "speed": 1.0,
        "audio_config": {
            "sample_rate": 48000,
            "num_channels": 1,
            "sample_width": 2,
            "encoding": "linear_pcm",
            "container": "wav"
        }
    }

    try:
        response = requests.post(
            TTS_URL,
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT
        )

        if not response.ok:
            raise RuntimeError(
                f"Gnani TTS error ({response.status_code}): "
                f"{response.text[:1000]}"
            )

        return response.content

    except requests.RequestException as error:
        raise RuntimeError(
            f"Could not connect to Gnani TTS: {error}"
        ) from error