import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import APIHTTPRequestError, ServerError

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

SUCCESSFUL_SENT_MESSAGE = 'Сообщение {message} успешно отправлено'
UNSUCCESSFUL_SENT_MESSAGE = 'Не удалось отправить сообщение "{message}"'
STATUS_MESSAGE = 'Изменился статус проверки работы "{homework_name}".{verdict}'
UNEXPECTED_STATUS = 'Неожиданный статус домашней работы:"{status}"'
UNEXPECTED_TYPE = 'Неожиданный тип содержимого:{type}'
UNEXPECTED_API_RESPONSE = (
    'Ответ API не соответствует документации({response}).{error}')
API_FAILED_RESPONSE = (
    'Эндпоинт API {ENDPOINT} недоступен. Код ответа API: {status_code}. '
    'Header: {HEADERS}. Timestamp: {timestamp}'
)
API_FAILED_REQUEST = (
    'Ошибка запроса к API:{error}, Эндпоинт API: {ENDPOINT}, '
    'Header: {HEADERS}, Timestamp: {timestamp}'
)
NO_KEY = 'Отсутствует ключ {key}'
NO_VARIABLE = 'Отсутствует обязательная переменная окружения'
ERROR_GLOBAL = 'Ошибка в работе бота: {error}'


logging.basicConfig(
    level=logging.INFO,
    filename=__file__ + '.log',
    filemode='a'
)
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(stream=sys.stdout)
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
            logger.critical(NO_VARIABLE)
            raise ValueError(NO_VARIABLE)
        return all({PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID})


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(SUCCESSFUL_SENT_MESSAGE.format(message=message))
    except telegram.TelegramError:
        logger.exception(UNSUCCESSFUL_SENT_MESSAGE.format(message=message))


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        if response.status_code != HTTPStatus.OK:
            raise APIHTTPRequestError(API_FAILED_RESPONSE.format(
                ENDPOINT=ENDPOINT,
                HEADERS=HEADERS,
                status_code=response.status_code,
                timestamp=timestamp)
            )
        if not response.json():
            logger.exception(API_FAILED_RESPONSE.format(
                ENDPOINT=ENDPOINT,
                HEADERS=HEADERS,
                status_code=response.status_code,
                timestamp=timestamp)
            )
            raise ServerError(API_FAILED_RESPONSE.format(
                ENDPOINT=ENDPOINT,
                HEADERS=HEADERS,
                status_code=response.status_code,
                timestamp=timestamp)
            )
        return response.json()
    except requests.RequestException as error:
        logger.exception(API_FAILED_REQUEST.format(
            error=error,
            ENDPOINT=ENDPOINT,
            HEADERS=HEADERS,
            timestamp=timestamp)
        )
        raise ServerError(API_FAILED_REQUEST.format(
            error=error,
            ENDPOINT=ENDPOINT,
            HEADERS=HEADERS,
            timestamp=timestamp)
        )


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    try:
        if not isinstance(response, dict):
            raise TypeError(UNEXPECTED_TYPE.format(type=type(response)))
        if 'homeworks' not in response.keys():
            raise KeyError(NO_KEY.format(key='homeworks'))
        if type(response['homeworks']) is not list:
            raise TypeError(
                UNEXPECTED_TYPE.format(type=type(response['homeworks'])))
        return response.get('homeworks')
    except TypeError as error:
        logger.exception(error)
        raise TypeError(UNEXPECTED_API_RESPONSE.format(
            response=response, error=error))


def parse_status(homework):
    """Возвращает статус домашней работы."""
    try:
        if not homework.get('homework_name'):
            raise ValueError(NO_KEY.format(key='homework_name'))
        status = homework.get('status')
        if status not in HOMEWORK_VERDICTS.keys():
            raise ValueError(UNEXPECTED_STATUS.format(status=status))
        homework_name = homework.get('homework_name')
        verdict = HOMEWORK_VERDICTS[status]
        return STATUS_MESSAGE.format(
            homework_name=homework_name, verdict=verdict)
    except Exception as error:
        logger.exception(error)
        raise ValueError(error)


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        api_answer = get_api_answer(timestamp)
        homeworks = check_response(api_answer)
        try:
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
                logger.info(SUCCESSFUL_SENT_MESSAGE.format(message=message))
        except Exception as error:
            send_message(bot, ERROR_GLOBAL.format(error=error))
            logger.exception(error)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt as error:
        logger.exception(error)

    # for testing
    # from unittest import TestCase, mock, main as uni_main
    # # JSON = {'error': 'testing'}
    # JSON = {'homeworks': [{'homework_name': 'test', 'status': 'approved'}]}
    # class TestReq(TestCase):
    #     @mock.patch('requests.get')
    #     def test_error(self, rq_get):
    #         resp = mock.Mock()
    #         resp.json = mock.Mock(return_value=JSON)
    #         rq_get.return_value = resp
    #         main()
    # uni_main()
