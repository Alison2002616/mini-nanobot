from typing import Any, Dict, List, Type

from minibot.Providers.base import LLMProvider
from minibot.Providers.errors import ProviderConfigError


DEFAULT_PROVIDER = "deepseek"


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers = {}  # type: Dict[str, Type[LLMProvider]]

    def register(self, name: str, provider_class: Type[LLMProvider]) -> Type[LLMProvider]:
        if not name:
            raise ProviderConfigError("provider name cannot be empty.")
        if name in self._providers:
            return self._providers[name]

        self._providers[name] = provider_class
        return provider_class

    def get(self, name: str) -> Type[LLMProvider]:
        if name not in self._providers:
            raise ProviderConfigError("unknown provider: {}".format(name))

        return self._providers[name]

    def create(self, name: str, **config: Any) -> LLMProvider:
        provider_class = self.get(name)
        return provider_class(**config)

    def list_providers(self) -> List[str]:
        return list(self._providers.keys())


provider_registry = ProviderRegistry()

