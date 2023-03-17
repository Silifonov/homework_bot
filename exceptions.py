class EnvironmentVariableDoesNotExist(Exception):
    """Исключение выпадающее при недоступности переменных окружения."""

    pass


class EndpointDisable(Exception):
    """Исключение выпадающее при недоступности endpoint.
    HTTPStatus отличен от 'ОК' (200).
    """

    pass
