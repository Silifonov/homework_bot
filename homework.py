import os
import requests
import logging
import telegram
import time
from typing import Optional
from sys import stdout
from dotenv import load_dotenv
from http import HTTPStatus
from exceptions import (
    EnvironmentVariableDoesNotExist,
    EndpointDisable,
)


load_dotenv()

PRACTICUM_TOKEN: str = os.getenv("PRACTICUM_TOKEN", "")
TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

RETRY_PERIOD: int = 600
ENDPOINT: str = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS: dict[str, str] = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS: dict = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens() -> None:
    """Проверяет доступность переменных окружения."""
    env_vars = {
        "PRACTICUM_TOKEN": PRACTICUM_TOKEN,
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    }
    # в такой реализации исключение выпадет при первом же пустом токене,
    # а как можно реализовать, чтобы был проверен весь словарь до конца,
    # и выпали ошибки сразу со всеми проблемными токенами?
    for var in env_vars:
        if not env_vars[var]:
            raise EnvironmentVariableDoesNotExist(
                f"Отсутствует обязательная переменная окружения: '{var}'.")


def send_message(bot: telegram.Bot, message: str) -> None:
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f"Сообщение отправлено в Telegram: '{message}' ")
    except Exception as error:
        logging.error(f"Cбой при отправке сообщения в Telegram: '{error}'")


def get_api_answer(timestamp: int) -> dict:
    """Запрос к эндпоинту API-сервиса.

    Делает запрос к эндпоинту API-сервиса,
    возвращает ответ, приведенный к типам данных Python.
    """
    try:
        payload = {'from_date': timestamp}
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.RequestException as error:
        raise EndpointDisable(f"Неуспешный запрос: '{error}'.")
    if response.status_code != HTTPStatus.OK:
        raise EndpointDisable(
            f"Endpoint не доступен, HTTPStatus: {response.status_code}")
    logging.info(response.text)
    try:
        return response.json()
    except requests.JSONDecodeError as error:
        raise requests.JSONDecodeError(
            f"Ошибка преобразования в JSON: {error}")


def check_response(response: Optional[dict]) -> Optional[list]:
    """Проверяет ответ API."""
    if not isinstance(response, dict):
        raise TypeError("Ответ API не соответствует типу 'dict'.")
    if "homeworks" not in response:
        raise KeyError("Ответ API не содержит ключа 'homeworks'")
    if "current_date" not in response:
        raise KeyError("Ответ API не содержит ключа 'current_date'")
    if not isinstance(response["homeworks"], list):
        raise TypeError(
            "Данные ключа 'homeworks' не соответствует типу 'list'.")
    return response.get("homeworks")


def parse_status(homework: dict) -> str:
    """Извлекает статус домашней работы, возворощает сообщение."""
    logging.info(homework)
    if "homework_name" not in homework:
        raise KeyError("Ключ 'homework_name' отсутствует в 'homework'")
    if homework.get("status") not in HOMEWORK_VERDICTS:
        raise KeyError(f"Неизвестный статус: '{homework['status']}'")
    homework_name = homework.get("homework_name")
    lesson_name = homework.get("lesson_name")
    status = homework.get("status")
    verdict = HOMEWORK_VERDICTS[status]
    return (f'Изменился статус проверки работы "{homework_name}".\n'
            f'Спринт "{lesson_name}".\n'
            f'{verdict}')


def main() -> None:
    """Основная логика работы бота."""
    # Настройка логирования
    logging.basicConfig(
        stream=stdout,
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    try:
        check_tokens()
    except EnvironmentVariableDoesNotExist as error:
        logging.critical(f'{error} Программа принудительно остановлена.')
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    send_message(
        bot,
        f"Проверяю статус домашней работы каждые {RETRY_PERIOD} секунд")
    timestamp = int(time.time())
    previous_error_message = ""
    previous_message = ""
    while True:
        try:
            logging.info(f"Timestamp for checking {timestamp}")
            response = get_api_answer(timestamp)
            timestamp = response["current_date"]
            logging.info(f"Timestamp for next checking {timestamp}")
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                if message != previous_message:
                    send_message(bot, message)
                    previous_message = message
            else:
                logging.debug(
                    "Домашняя работа отсутствует или ее статус не изменился.")
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if previous_error_message != message:
                send_message(bot, message)
                previous_error_message = message
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logging.debug("Работа бота прервана вручную")
