class ProblemDescriptions(Exception):
    """Описания проблемы."""

    pass


class NotForSending(Exception):
    """Не для пересылки в телеграм."""

    pass


class TelegramError(NotForSending):
    """Ошибка телеграма."""

    pass


class ConnectinError(Exception):
    """Не верный код ответа."""

    pass


class EmptyResponseFromAPI(NotForSending):
    """Пустой ответ от API."""

    pass


class InvalidResponseCode(Exception):
    """Не верный код ответа."""

    pass


class HomeWorkIsNotList(Exception):
    """Проверка домашней работы."""

    pass


class GetApiException(Exception):
    """Проверка API."""

    pass


class StatusCodeException(Exception):
    """Статус."""

    pass