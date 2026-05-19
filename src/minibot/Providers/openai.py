from minibot.Providers.openai_compatible import OpenAICompatibleProvider
from minibot.Providers.registry import provider_registry


class OpenAIProvider(OpenAICompatibleProvider):
    name = "openai"
    default_base_url = "https://api.openai.com/v1"
    default_model = "gpt-4o-mini"


provider_registry.register("openai", OpenAIProvider)

