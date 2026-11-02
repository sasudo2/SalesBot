from typing import Protocol
from app.models import ToolSpec, LLMResponse, ToolCalls, Usage

class Provider(Protocol):
    name: str

    async def complete(self, message:str, tools:list[ToolSpec], **opt)->LLMResponse: ...

class LLMRepository:
    def __init__(self):
        self._repository: dict[str, type[Provider]] = {}
        self._instance: dict[str, Provider] = {}
        self._provider: Provider = None
        self._default: str = "fake_provider"

    def _get(self, name: str)->Provider:
        """return the instance of the provider 
        if available in self.instance else add 
        it to self.instance and returns the instance"""
        if name not in self._instance:
            self._instance[name] = self._repository[name]()
        return self._instance[name]

    def add_provider(self, name:str, provider: type[Provider]):
        """add provider classes to self._repository"""
        self._repository[name] = provider

    async def complete(self, prompt: str, tools: list[ToolSpec] | None = None, provider: str | None = None,  **opt) -> LLMResponse:
        name = provider or self._default
        if name is None:
            raise ValueError("No provider given or no default set")
        return await self._get(name).complete(prompt, tools, **opt)
        

class FakeProvider():
    def __init__(self):
        self.name = "fake_provider"

    async def complete(self, message:str, tools:list[ToolSpec], **opt)->LLMResponse:
        return LLMResponse(
            content="Hello! this is a fake LLM",
            tool_calls = [ToolCalls(id="00", name="fake_tool", arguments={})],
            usage = Usage(input_token = 1, outpout_token = 1)
        )