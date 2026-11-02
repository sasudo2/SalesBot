from app.llm.openai_provider import OpenAIProvider


class GeminiProvider(OpenAIProvider):
    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        timeout: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        super().__init__(
            api_key,
            model,
            timeout,
            max_retries,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
