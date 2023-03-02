import datetime
import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from exceptions import NoCurrentDateKeyInResponseError

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
FROM_DATE = 0

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}
logger = logging.getLogger(__name__)
CURRENT_TIME = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def check_tokens():
    """Проверка работы переменных."""
    return all([TELEGRAM_TOKEN, PRACTICUM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logger.info(f'Бот отправил сообщение "{message}"')
    except telegram.TelegramError as error:
        logging.error(f'Gри отправке сообщения возникла ошибка: {error}')
    else:
        logging.debug('Сообщение отправлено успешно')


def get_api_answer(current_timestamp):
    """Проверка статуса домашней работы."""
    timestamp = current_timestamp or int(time.time())
    params = {
        'from_date': timestamp
    }
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params,
        )
        if homework_statuses.status_code != HTTPStatus.OK:
            raise Exception(f'Недоступность эндпойнта '
                            f'{homework_statuses.status_code}')
        return homework_statuses.json()
    except Exception as error:
        raise Exception(f'Сбой при запросе к эндпойнту: {error}')


def check_response(response):
    """Проверка валидности ответа."""
    if not isinstance(response, dict):
        raise TypeError('Ответ пришел не в виде словаря.')
    if 'homeworks' not in response:
        raise KeyError(
            'В ответе нет ключа homeworks'
        )
    if 'current_date' not in response:
        raise NoCurrentDateKeyInResponseError(
            'В ответе нет ключа current_date'
        )
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            'Домашние работы приходят не в виде списка в ответ от API'
        )
    return homeworks


def parse_status(homework):
    """Парсинг ответов."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует "homework_name" в  API')
    if 'status' not in homework:
        raise KeyError('Отсутствует "status" в  API')
    if homework['status'] not in HOMEWORK_VERDICTS:
        raise KeyError('Не проверенный статус в  API')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}" {verdict}'


def main() -> None:
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствует одна из обязательных '
                        'переменных окружения')
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_message = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if homework:
                message = parse_status(homework[0])
                if message != last_message:
                    last_message = message
                    send_message(bot, message)
            current_timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format=(
            '%(asctime)s, %(levelname)s, Путь - %(pathname)s, '
            'Файл - %(filename)s, Функция - %(funcName)s, '
            'Номер строки - %(lineno)d, %(message)s'
        ),
        handlers=[logging.FileHandler('log.txt', encoding='UTF-8'),
                  logging.StreamHandler(sys.stdout)])
    main()
