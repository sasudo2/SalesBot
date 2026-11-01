from fastapi import HTTPException
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.state.conversation_state import ConversationRecord
from pathlib import Path
from app.config import setting
import pandas as pd
import httpx
import logging
import asyncio
logger = logging.getLogger(__name__)

async def call_llm(prompt: list[dict], max_token=1024):
    try:
        async with httpx.AsyncClient(
            timeout=90,
        ) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {setting.openrouter_token.get_secret_value()}",
                },
                json={
                    "model": setting.openrouter_model,
                    "messages": prompt,
                    "max_tokens": max_token,
                },
            )
            response.raise_for_status()
            payload = response.json()
            choices = payload.get("choices", [])
            answer = choices[0]["message"].get("content") if choices else None

    except  httpx.HTTPStatusError as error:
        provider_status = error.response.status_code
        logger.warning("OpenRouter inference failed with HTTP %s: %s", provider_status, error.response.text)
        details = {
            401: "OpenRouter authentication failed. Check OPENROUTER_TOKEN.",
            402: "OpenRouter credits are exhausted. Select a free model or add credits.",
            429: "OpenRouter rate limit reached. Try again later; free models have limited quotas.",
        }
        raise HTTPException(
            status_code=503 if provider_status in (402, 429, 503) else 502,
            detail=f"{error.response.text} OpenRouter request failed. Try again later.",
        ) from None
    except Exception:
        logger.exception("OpenRouter inference failed")
        raise HTTPException(
            status_code = 502,
            detail = "OpenRouter request failed. Check provider access and availability.",
        ) from None

    return answer


async def generate_document_summary(document_path: Path)->str:
    df = pd.read_csv(document_path)

    essential_cols = [
        "product_id", "product_name", "description", "brand", "category",
        "root_category", "final_price", "currency", "in_stock", "rating",
        "reviews_count", "color", "size",
    ]
    available_cols = [c for c in essential_cols if c in df.columns]
    catalog_text = df[available_cols].to_json(orient="records")

    system_prompt = (
        "You are an inventory summarizer. Below is the product catalog data in JSON format. "
        "Create a concise, comprehensive summary of the product categories, popular items, but never the exact price figures"
        "and key features so that a sales agent can easily reference this information to help customers:\n\n"
        f"{catalog_text}"
    )

    prompt = [{
        "role":"system",
        "content":system_prompt
    }]

    response = await call_llm(prompt=prompt, max_token=4096);
    def _write():
        with open(setting.summary_path, 'w', encoding="utf-8") as f:
            print("writing file")
            f.write(response)

    await asyncio.to_thread(_write)


async def generate_answer(query: str, conversation_id:UUID, db:AsyncSession):
    conversation = await db.get(ConversationRecord, conversation_id)
    conversation_history = conversation.conversation_history
    def _read():
            with open(setting.summary_path, 'w', encoding="utf-8") as f:
                return f.read()

    summary = await asyncio.to_thread(_read)

    messages = [
        {
            "role":"system",
            "content": (
                f"""You are an expert AI sales and shopping assistant for our e-commerce store. Your primary goal is to guide customers through their shopping journey, answer product inquiries, offer personalized recommendations based on our inventory summary, and help them find products that match their needs.

                    ### Core Guidelines & Persona:
                    1. **Tone & Style:** Be warm, professional, engaging, and persuasive. Treat every interaction like a top-tier retail consultation.
                    2. **Product Knowledge:** Rely strictly on the provided inventory summary and RAG context to describe product categories, features, and use cases. 
                    3. **Handling Prices:** Never guess or state exact price figures unless they are explicitly present in your verified context. If pricing is asked and unavailable, guide the customer to check the specific product listing or offer general value-based comparisons.
                    4. **Sales Approach:** Actively listen to customer queries, diagnose their preferences (e.g., skin type, style, budget, use case), and suggest the top 1-2 most relevant items from our catalog. Always follow up with a helpful question to keep the conversation moving forward (e.g., "Would you like to explore options for dry skin or combination skin?").
                    5. **Honesty & Boundaries:** If a product or feature is not available in our catalog, politely let the customer know rather than making up information. Never break character.

                    ### Context & Inventory Reference:
                    {summary}
                    """
            )
        },
        *conversation_history,
        {
            "role": "user",
            "content": (
                f"{query}"
            )
        }
    ]

    response = await call_llm(prompt = messages)
    conversation_history.append({"role":"user", "content":query})
    conversation_history.append({"role":"assistant", "content":response})
    conversation.conversation_history=conversation_history
    db.commit()
    return response


