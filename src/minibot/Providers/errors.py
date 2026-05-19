class ProviderError(Exception):
    pass


class ProviderConfigError(ProviderError):
    pass


class ProviderAuthError(ProviderError):
    pass


class ProviderRequestError(ProviderError):
    pass


class ProviderResponseError(ProviderError):
    pass


class ProviderStreamError(ProviderError):
    pass


class ProviderTimeoutError(ProviderError):
    pass

