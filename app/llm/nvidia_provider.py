from app.llm.openai_provider import OpenAIProvider


class NvidiaProvider(OpenAIProvider):
    name = "nvidia"

    def __init__(
        self,
        api_key: str,
        model: str = "nvidia/nemotron-3.5-super-vl-120b-a12b",
        timeout: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        super().__init__(
            api_key,
            model,
            timeout,
            max_retries,
            base_url="https://integrate.api.nvidia.com/v1",
        )
