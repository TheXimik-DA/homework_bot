import datetime
import logging
import os
import sys
import time
from http import HTTPStatus

import exceptions
import requests
import telegram
from dotenv import load_dotenv

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
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params,
        )
        if homework_statuses.status_code != HTTPStatus.OK:
            raise Exception(f'Недоступность эндпойнта '
                            f'{homework_statuses.status_code}')
        else:
            return homework_statuses.json()
    except Exception as error:
        raise Exception(f'Сбой при запросе к эндпойнту: {error}')


def check_response(response) -> list:
    """Проверка валидности ответа."""
    try:
        homeworks = response['homeworks']
    except KeyError:
        message = 'Ключ "homeworks" отсутствует в ответе API.'
        raise KeyError(message)
    if not isinstance(response, dict):
        raise TypeError(
            f'API должен возвращать словарь, получен {type(response)}.')
    if not isinstance(homeworks, list):
        raise TypeError(
            f'Значение по ключу "homeworks" должно быть списком, '
            f'Получено {type(homeworks)}.')
    return homeworks


def parse_status(homework):
    """Парсинг ответов."""
    if 'homework_name' not in homework:
        logger.error('Отсутствует "homework_name" в  API')
        raise KeyError('Отсутствует "homework_name" в  API')
    if 'status' not in homework:
        logger.error('Отсутствует "homework_status" в  API')
        raise KeyError('Отсутствует "status" в  API')
    if homework['status'] not in HOMEWORK_VERDICTS:
        logging.error('Не проверенный статус в  API')
        raise KeyError('Не проверенный статус в  API')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}" {verdict}'


def main() -> None:
    """Основная логика работы бота."""
    logging.info('Бот активен')
    if not check_tokens():
        logging.critical('Отсутствует нужное количество'
                         ' переменных окружения')
        sys.exit('Отсутсвуют все переменные окружения')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp: str = FROM_DATE
    last_error_message: str = ''
    telegram_error_check: bool = False
    while True:
        try:
            result: dict = get_api_answer(timestamp)
            homeworks: list = check_response(result)
            logging.info('Список домашних работ получен')
            if len(homeworks) > 0 and homeworks[0] != timestamp:
                send_message(bot, parse_status(homeworks[0]))
                timestamp = result['current_date']
        except (ConnectionError, TimeoutError) as error:
            if str(error) != last_error_message and not telegram_error_check:
                current_time = CURRENT_TIME
                message: str = (f'[{current_time}]'
                                f'Сбой в работе программы: {error}')
                logging.error(message)
                send_message(bot, message)
                last_error_message = str(error)
                telegram_error_check = True
        except telegram.error.TelegramError as error:
            current_time = CURRENT_TIME
            message: str = f'[{current_time}] Ошибка Telegram: {error}'
            logging.error(message)
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
