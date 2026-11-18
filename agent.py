import os

from dotenv import load_dotenv
from loguru import logger

from pipecat.frames.frames import (
    TTSSpeakFrame,
    TranscriptionFrame
)

from pipecat.processors.frame_processor import (
    FrameDirection,
    FrameProcessor
)

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker

from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport

from pipecat.serializers.protobuf import ProtobufFrameSerializer
from pipecat.transcriptions.language import Language

from pipecat.transports.base_transport import BaseTransport
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams

from pipecat.workers.runner import WorkerRunner

from pipecat_gnani import GnaniSTTService, GnaniTTSService

from ledger import process_command


load_dotenv(override=True)


# SUPPORTED LANGUAGES

LANGUAGES = {
    "en-IN": Language.EN_IN,
    "hi-IN": Language.HI_IN,
    "kn-IN": Language.KN_IN,
    "ta-IN": Language.TA_IN,
    "te-IN": Language.TE_IN,
    "ml-IN": Language.ML_IN,
    "mr-IN": Language.MR_IN,
    "gu-IN": Language.GU_IN,
    "bn-IN": Language.BN_IN,
    "pa-IN": Language.PA_IN
}


GREETINGS = {
    "en-IN": (
        "Hello! I am VoiceKhata, an AI assistant for your shop. "
        "Tell me a customer credit or payment."
    ),
    "hi-IN": (
        "Namaste! Main VoiceKhata AI assistant hoon. "
        "Aap customer ka udhaar ya payment bata sakte hain."
    ),
    "kn-IN": (
        "Namaskara! Naanu VoiceKhata AI assistant. "
        "Customer credit athava payment heli."
    )
}


# WEBSOCKET TRANSPORT

TRANSPORT_PARAMS = {
    "websocket": lambda: FastAPIWebsocketParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        audio_in_sample_rate=16000,
        audio_out_sample_rate=16000,
        add_wav_header=False,
        serializer=ProtobufFrameSerializer()
    )
}


def get_selected_language(runner_args):
    language_code = "en-IN"

    try:
        language_code = (
            runner_args.websocket.query_params.get(
                "language", "en-IN"
            )
        )
    except Exception:
        pass

    if language_code not in LANGUAGES:
        language_code = "en-IN"

    return language_code


# COMMAND PROCESSOR

class VoiceKhataCommandProcessor(FrameProcessor):

    def __init__(self, language_code):
        super().__init__()
        self.language_code = language_code

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            # Forward transcript to downstream processors.
            await self.push_frame(frame, direction)

            transcript = str(frame.text).strip()

            if not transcript:
                return

            logger.info(f"VoiceKhata transcript: {transcript}")

            try:
                reply = process_command(
                    transcript,
                    language_code=self.language_code
                )
            except Exception:
                logger.exception("Ledger command failed")
                reply = (
                    "Sorry, I could not process that transaction. "
                    "Please try again."
                )

            await self.push_frame(
                TTSSpeakFrame(text=reply),
                FrameDirection.DOWNSTREAM
            )

            return

        await self.push_frame(frame, direction)


# BOT PIPELINE

async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):

    api_key = os.getenv("GNANI_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError(
            "GNANI_API_KEY is missing. Check your .env file."
        )

    language_code = get_selected_language(runner_args)
    language = LANGUAGES[language_code]

    logger.info(
        f"Starting VoiceKhata in language: {language_code}"
    )

    # GNANI STREAMING SPEECH RECOGNITION
    stt = GnaniSTTService(
        api_key=api_key,
        sample_rate=16000,
        settings=GnaniSTTService.Settings(
            model="prisma-v3.0",
            language=language,
            format="transcribe",
            keywords=[
                "VoiceKhata",
                "kirana",
                "Ramesh",
                "Suresh",
                "Anjali",
                "Rahul",
                "customer",
                "credit",
                "udhaar",
                "payment",
                "balance",
                "rupees",
                "cash sale"
            ]
        )
    )

    # GNANI STREAMING TEXT TO SPEECH
    voice = os.getenv("GNANI_TTS_VOICE", "Chetana").strip()

    tts = GnaniTTSService(
        api_key=api_key,
        settings=GnaniTTSService.Settings(
            model="timbre-v3.0",
            voice=voice,
            language=language
        )
    )

    command_processor = VoiceKhataCommandProcessor(
        language_code=language_code
    )

    pipeline = Pipeline([
        transport.input(),
        stt,
        command_processor,
        tts,
        transport.output()
    ])

    worker = PipelineWorker(
        pipeline=pipeline,
        params=PipelineParams(
            audio_in_sample_rate=16000,
            audio_out_sample_rate=16000,
            enable_metrics=True,
            enable_usage_metrics=True
        ),
        enable_rtvi=True,
        idle_timeout_secs=300
    )

    runner = WorkerRunner()

    await runner.add_workers(worker)

    @worker.rtvi.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        greeting = GREETINGS.get(
            language_code,
            GREETINGS["en-IN"]
        )

        await worker.queue_frame(
            TTSSpeakFrame(text=greeting)
        )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("VoiceKhata client connected.")

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("VoiceKhata client disconnected.")

    await runner.run(worker)


# APPLICATION ENTRY POINT

async def bot(runner_args: RunnerArguments):
    transport = await create_transport(
        runner_args,
        TRANSPORT_PARAMS
    )

    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()