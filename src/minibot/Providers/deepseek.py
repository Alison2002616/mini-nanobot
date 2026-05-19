from minibot.Providers.openai_compatible import OpenAICompatibleProvider
from minibot.Providers.registry import provider_registry


class DeepSeekProvider(OpenAICompatibleProvider):
    name = "deepseek"
    default_base_url = "https://api.deepseek.com/v1"
    default_model = "deepseek-v4-flash"


provider_registry.register("deepseek", DeepSeekProvider)

