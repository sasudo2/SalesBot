from app.llm.openai_provider import OpenAIProvider


class OpenRouterProvider(OpenAIProvider):
    name = "openrouter"

    def __init__(
        self,
        api_key: str,
        model: str = "openrouter/free",
        timeout: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        super().__init__(
            api_key,
            model,
            timeout,
            max_retries,
            base_url="https://openrouter.ai/api/v1",
        )
