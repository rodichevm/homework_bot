import logging
import os
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv

from exceptions import APIHTTPRequestError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(
    __file__ + '.log', maxBytes=50000000, backupCount=5)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s, %(funcName)s, %(levelname)s, %(message)s'
)
handler.setFormatter(formatter)


def check_tokens():
    """Проверяем доступность переменных окружения."""
    tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    for token in tokens:
        if token is None:
            logger.critical('Отсутствует токен')
        return token


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(
            f'Сообщение {message} успешно отправлено в Telegram чат')
    except telegram.TelegramError:
        logger.exception(
            f'Не удалось отправить сообщение {message}в Telegram чат')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API."""
    # применить последний рубеж
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
    except requests.RequestException as error:
        raise Exception(
            f'Ошибка запроса к API:{error}, '
            f'Эндпоинт: {ENDPOINT}, Header: {HEADERS}', {timestamp}
        )
    if response.status_code != HTTPStatus.OK:
        raise APIHTTPRequestError(
            f'Эндпоинт API {ENDPOINT} недоступен. '
            f'Код ответа API: {response.status_code}'
        )
    if response.json():
        #прописать страховку на случай отказа от обслуживания
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if type(response) is not dict:
        # "Это dict или его наследник"
        raise TypeError(f'API вернул не словарь, а {type(response)}')
    if 'homeworks' in response.keys():
        if type(response['homeworks']) is not list:
            # logger.error
            raise TypeError(f'Тип содержимого словаря не является не списком, а {}')
        return response.get('homeworks')
    logger.exception('Хрен знает что такое последний рубеж')
    raise KeyError('В ответе API в словаре неверные ключи')


def parse_status(homework):
    """Возвращает статус домашней работы."""
    if not homework.get('homework_name'):
        logger.error('Отсутствует ключ homework_name')
        raise ValueError
    if homework.get('status') not in HOMEWORK_VERDICTS.keys():
        logger.error('Отсутствует документированный статус домашней работы')
        raise ValueError
    homework_name = homework.get('homework_name')
    verdict = HOMEWORK_VERDICTS[homework.get('status')]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствует обязательная переменная окружения')
        raise ValueError
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            api_answer = get_api_answer(timestamp)
            homeworks = check_response(api_answer)
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
            else:
                send_message(bot, 'Обновлений нет')
                logger.debug('Сообщение c отсутствием успешно отправлено')
        except Exception as message:
            send_message(bot, f'Сбой в работе программы: {message}')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logging.exception('Бот остановлен')
