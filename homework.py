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
    except telegram.TelegramError as error:
        logging.error(f'Gри отправке сообщения возникла ошибка: {error}')
    else:
        logging.debug('Сообщение отправлено успешно')


def get_api_answer(current_timestamp):
    """Проверка статуса домашней работы."""
    timestamp = current_timestamp or int(time.time())
    params_request = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp},
    }
    try:
        logging.info(
            'Старт запроса: url = {url},'
            'headers = {headers},'
            'params = {params}'.format(**params_request))
        homework_status = requests.get(**params_request)
        if homework_status.status_code != HTTPStatus.OK:
            raise exceptions.InvalidResponseCode(
                'Не удалось получить ответ API, '
                f'Ошибка: {homework_status.status_code}'
                f'Причина: {homework_status.reason}'
                f'Текст: {homework_status.text}')
        return homework_status.json()
    except Exception:
        raise exceptions.ConnectinError(
            'Не корректный код ответа, параметры запроса: url = {url},'
            'headers = {headers},'
            'params = {params}'.format(**params_request))


def check_response(response) -> list:
    """Проверка валидности ответа."""
    if not isinstance(response, dict):
        raise TypeError(
            f'API должен возвращать словарь, получен {type(response)}.')
    if 'homeworks' not in response:
        raise KeyError(
            'Ключ "homeworks" отсутствует в ответе API.')
    if not isinstance(response['homeworks'], list):
        raise TypeError(
            f'Значение по ключу "homeworks" должно быть списком, '
            f'Получено {type(response["homeworks"])}.')
    return response['homeworks']


def parse_status(homework):
    """Парсинг ответов."""
    if 'homework_name' not in homework:
        raise KeyError('В ответе отсутсвует ключ homework_name')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус работы - {homework_status}')
    return (
        'Изменился статус проверки работы "{homework_name}" {verdict}'
    ).format(
        homework_name=homework_name,
        verdict=HOMEWORK_VERDICTS[homework_status]
    )


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
                current_time = datetime.datetime.now().strftime(
                    '%Y-%m-%d %H:%M:%S'
                )
                message: str = (f'[{current_time}]'
                                f'Сбой в работе программы: {error}')
                logging.error(message)
                send_message(bot, message)
                last_error_message = str(error)
                telegram_error_check = True
        except telegram.error.TelegramError as error:
            current_time = datetime.datetime.now().strftime(
                '%Y-%m-%d %H:%M:%S'
            )
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
