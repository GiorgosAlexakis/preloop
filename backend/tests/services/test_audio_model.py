"""Tests for audio model provider backends."""

import json
from types import SimpleNamespace

from preloop.services.audio_model import (
    AudioModelResolution,
    GoogleSpeechAudioProviderBackend,
)


def test_google_speech_backend_posts_recognize_payload(monkeypatch):
    """Google STT should call Speech-to-Text with the configured model."""
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return json.dumps(
                {
                    "results": [
                        {"alternatives": [{"transcript": "hello hermes"}]},
                    ]
                }
            ).encode()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode())
        return FakeResponse()

    monkeypatch.setattr(
        "preloop.services.audio_model.urllib_request.urlopen", fake_urlopen
    )

    resolution = AudioModelResolution(
        ai_model=SimpleNamespace(id="model-id"),
        model_identifier="latest_short",
        provider_name="google",
        api_key="google-key",
        api_endpoint=None,
        model_parameters={"language_code": "en-US"},
    )

    transcript = GoogleSpeechAudioProviderBackend().transcribe(
        resolution=resolution,
        audio=b"audio-bytes",
        filename="clip.webm",
        content_type="audio/webm",
    )

    assert transcript == "hello hermes"
    assert captured["url"].endswith("?key=google-key")
    assert captured["timeout"] == 60
    assert captured["body"]["config"]["model"] == "latest_short"
    assert captured["body"]["config"]["encoding"] == "WEBM_OPUS"
    assert captured["body"]["audio"]["content"]
