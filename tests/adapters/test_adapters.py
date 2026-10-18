import io
import threading
import unittest
import wave

from voice_agent.adapters.audio import SoxAudioInput
from voice_agent.adapters.config import DeepgramConfig, KittenTTSConfig
from voice_agent.adapters.deepgram import DeepgramSTT
from voice_agent.adapters.errors import (
    AdapterUnavailableError,
    ConfigurationError,
    ProviderCancelledError,
    ProviderRequestError,
)
from voice_agent.adapters.kitten_tts import KittenTTS


class AdapterTests(unittest.TestCase):
    def test_deepgram_configuration_uses_documented_defaults_without_leaking_key(self):
        config = DeepgramConfig.from_environment({"DEEPGRAM_API_KEY": "secret", "DEEPGRAM_LANGUAGE": "es-419"})
        self.assertEqual((config.model, config.language, config.sample_rate, config.channels), ("nova-3", "es-419", 16000, 1))
        self.assertNotIn("secret", repr(config))

    def test_deepgram_requires_key(self):
        with self.assertRaises(ConfigurationError):
            DeepgramConfig.from_environment({})

    def test_deepgram_maps_transport_failure_and_honors_cancellation(self):
        token = threading.Event()
        token.set()
        with self.assertRaises(ProviderCancelledError):
            DeepgramSTT(DeepgramConfig("key"), transport=lambda *_: "never").transcribe([b"pcm"], token)

        def failing(*_):
            raise RuntimeError("network")

        with self.assertRaises(ProviderRequestError):
            DeepgramSTT(DeepgramConfig("key"), transport=failing).transcribe([b"pcm"], threading.Event())

    def test_kitten_tts_uses_official_model_and_weights_mapping(self):
        calls = []

        class Model:
            def generate(self, text, voice):
                self.asserted = (text, voice)
                return [-1.0, 0.0, 1.0]

        def loader(model, weights):
            calls.append((model, weights))
            return Model()

        adapter = KittenTTS(loader=loader)
        output = adapter.synthesize("hola", threading.Event())
        with wave.open(io.BytesIO(output)) as wav:
            self.assertEqual((wav.getnchannels(), wav.getframerate(), wav.getnframes()), (1, 24000, 3))
        self.assertEqual(calls, [("KittenML/kitten-tts-2", "emb4")])

    def test_kitten_tts_maps_missing_runtime_and_cancellation(self):
        with self.assertRaises(AdapterUnavailableError):
            KittenTTS(loader=lambda *_: (_ for _ in ()).throw(AdapterUnavailableError("missing"))).synthesize("hola", threading.Event())

        token = threading.Event()
        token.set()
        with self.assertRaises(ProviderCancelledError):
            KittenTTS(loader=lambda *_: None).synthesize("hola", token)

    def test_audio_input_maps_missing_executable_and_cancellation(self):
        def missing(*args, **kwargs):
            raise OSError("not found")

        with self.assertRaises(AdapterUnavailableError):
            list(SoxAudioInput(popen=missing).capture(threading.Event()))

        token = threading.Event()
        token.set()
        with self.assertRaises(ProviderCancelledError):
            list(SoxAudioInput(popen=lambda *args, **kwargs: None).capture(token))

    def test_deepgram_http_path_is_explicitly_non_streaming_for_now(self):
        # The current HTTP transport buffers PCM before one request; Pi's streaming
        # WebSocket baseline remains a deliberate follow-up boundary.
        received = []

        def transport(payload, config, cancellation):
            received.append(payload)
            return "hola"

        result = DeepgramSTT(DeepgramConfig("key"), transport=transport).transcribe([b"a", b"b"], threading.Event())
        self.assertEqual(result, "hola")
        self.assertEqual(received, [b"ab"])


if __name__ == "__main__":
    unittest.main()
