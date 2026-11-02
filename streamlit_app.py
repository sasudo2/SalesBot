"""Run with: uv run --extra ui streamlit run streamlit_app.py."""

import os
from uuid import uuid4

import httpx
import streamlit as st
from pydantic import ValidationError

from app.domain.schemas import ChatResponse, ErrorResponse


def _reset_chat() -> None:
    st.session_state.conversation_id = str(uuid4())
    st.session_state.messages = []
    st.session_state.cart = None
    st.session_state.handoff = False


def _main() -> None:
    st.set_page_config(page_title="SalesBot")
    st.title("SalesBot")
    st.caption("Search products, ask questions, and manage your cart.")

    with st.sidebar:
        st.header("Connection")
        base_url = (
            st.text_input(
                "Backend URL", value=os.getenv("SALESBOT_API_URL", "http://localhost:8000")
            )
            .strip()
            .rstrip("/")
        )
        api_key = st.text_input("API key", type="password", value=os.getenv("API_KEY", ""))
        st.caption("Use the backend's API_KEY, not an OpenAI or Anthropic key.")
        if "conversation_id" not in st.session_state:
            _reset_chat()
        if st.session_state.get("backend_url") != base_url:
            st.session_state.backend_url = base_url
            _reset_chat()
        if st.button("New conversation"):
            _reset_chat()
        st.caption(f"Conversation: {st.session_state.conversation_id}")
        st.caption("Starting a new chat does not cancel the previous cart or order.")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.text(message["content"])

    query = st.chat_input("What are you looking for?", max_chars=2000)
    if query:
        st.session_state.messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.text(query)
        try:
            url = httpx.URL(base_url)
            if url.scheme not in ("http", "https") or not url.host:
                raise ValueError("Backend URL must be an HTTP or HTTPS address.")
            with st.spinner("Thinking..."):
                response = httpx.post(
                    f"{base_url}/chat",
                    json={
                        "conversation_id": st.session_state.conversation_id,
                        "query": query,
                        "channel": "web",
                    },
                    headers={"X-API-Key": api_key} if api_key else {},
                    timeout=120.0,
                )
            if response.is_error:
                try:
                    error = ErrorResponse.model_validate_json(response.content)
                except ValidationError:
                    st.error(f"Backend returned HTTP {response.status_code}.")
                else:
                    st.error(f"{error.message} ({error.code})")
                    if error.request_id:
                        st.caption(f"Request ID: {error.request_id}")
            else:
                result = ChatResponse.model_validate_json(response.content)
                if str(result.conversation_id) != st.session_state.conversation_id:
                    raise ValueError("Backend returned a different conversation ID.")
                st.session_state.messages.append({"role": "assistant", "content": result.reply})
                st.session_state.cart = result.cart
                st.session_state.handoff = result.handoff
                with st.chat_message("assistant"):
                    st.text(result.reply)
        except httpx.TimeoutException:
            st.error(
                "The request timed out. It may still complete on the server. "
                "Do not blindly repeat an order request."
            )
        except httpx.RequestError:
            st.error("Could not reach the backend. Check its URL and that uvicorn is running.")
        except (ValueError, httpx.InvalidURL):
            st.error("Invalid backend URL or response. Check the backend configuration and logs.")

    if st.session_state.handoff:
        st.info("This conversation has been handed to the shop team.")
    with st.sidebar:
        st.header("Cart")
        cart = st.session_state.cart
        if cart is None or not cart.items:
            st.caption("No items in the last received cart.")
        else:
            st.caption("Last received snapshot; availability may have changed.")
            for item in cart.items:
                st.text(f"{item.quantity} x {item.name}")
                st.text(f"{item.unit_price:,.2f} each; {item.line_total:,.2f} total")
            st.metric("Total", f"{cart.total:,.2f}")
            st.caption("Amounts use the backend catalogue currency.")
            if cart.status == "awaiting_confirmation":
                st.warning("Review the order and reply yes or no in chat.")


if __name__ == "__main__":
    _main()
