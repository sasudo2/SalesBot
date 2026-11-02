from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import httpx
import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

SCRIPT = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def _app():
    app = AppTest.from_file(str(SCRIPT)).run()
    assert not app.exception
    return app


def _response(app, status=200, **overrides):
    body = {
        "conversation_id": app.session_state.conversation_id,
        "reply": "Here is your cart.",
        "handoff": False,
        "cart": {
            "status": "awaiting_confirmation",
            "items": [{"product_id": "p", "name": "Product", "quantity": 2, "unit_price": "10.00"}],
            "total": "20.00",
        },
        **overrides,
    }
    return httpx.Response(status, json=body)


def test_chat_and_new_conversation():
    app = _app()
    original = app.session_state.conversation_id
    app.text_input[1].set_value("test-key").run()
    with patch("httpx.post", return_value=_response(app)) as post:
        app.chat_input[0].set_value("two please").run()
    assert not app.exception
    assert [m["role"] for m in app.session_state.messages] == ["user", "assistant"]
    assert app.metric[0].value == "20.00"
    assert post.call_args.kwargs["headers"] == {"X-API-Key": "test-key"}
    assert post.call_args.kwargs["json"] == {
        "conversation_id": original,
        "query": "two please",
        "channel": "web",
    }
    app.run()
    assert len(app.chat_message) == 2
    app.button[0].click().run()
    assert app.session_state.conversation_id != original
    assert app.session_state.messages == [] and app.session_state.cart is None


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        (httpx.TimeoutException("timeout"), "timed out"),
        (httpx.ConnectError("unavailable"), "Could not reach"),
        (httpx.Response(502, text="gateway"), "HTTP 502"),
        (httpx.Response(200, json={"wrong": "shape"}), "Invalid backend"),
        (
            httpx.Response(
                401,
                json={"code": "invalid_state", "message": "Invalid API key", "request_id": "r1"},
            ),
            "Invalid API key",
        ),
    ],
)
def test_errors(failure, message):
    app = _app()
    kwargs = (
        {"side_effect": failure} if isinstance(failure, Exception) else {"return_value": failure}
    )
    with patch("httpx.post", **kwargs):
        app.chat_input[0].set_value("hello").run()
    assert not app.exception
    assert message in app.error[0].value
    assert len(app.session_state.messages) == 1


def test_handoff_and_backend_change():
    app = _app()
    with patch("httpx.post", return_value=_response(app, handoff=True, cart=None)):
        app.chat_input[0].set_value("human please").run()
    assert app.info
    original = app.session_state.conversation_id
    app.text_input[0].set_value("http://localhost:9000").run()
    assert app.session_state.conversation_id != original
    assert app.session_state.messages == []
    with patch("httpx.post", return_value=_response(app, conversation_id=str(uuid4()))):
        app.chat_input[0].set_value("hello").run()
    assert app.error
