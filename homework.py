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
UNSUCCESSFUL_SENT_MESSAGE = (
    'Не удалось отправить сообщение "{message}. Ошибка:{error}"')
STATUS_MESSAGE = 'Изменился статус проверки работы "{homework_name}".{verdict}'
UNEXPECTED_STATUS = 'Неожиданный статус домашней работы:"{status}"'
UNEXPECTED_TYPE_DICT = 'Вместо типа dict получен:{type}'
UNEXPECTED_TYPE_LIST = 'Вместо типа list получен: {type}'
UNEXPECTED_API_RESPONSE = (
    'Ответ API не соответствует документации({response}).{error}')
API_FAILED_RESPONSE = (
    'Эндпоинт API {ENDPOINT} недоступен. Код ответа API: {status_code}. '
    'Header: {HEADERS}'
)
API_FAILED_REQUEST = (
    'Ошибка запроса к API:{error}, Эндпоинт API: {ENDPOINT}, '
    'Header: {HEADERS}, Timestamp: {timestamp}'
)
NO_KEY = 'Отсутствует ключ {key}'
NO_VARIABLE = 'Отсутствует обязательная переменная окружения {token}'
ERROR_GLOBAL = 'Ошибка в работе бота: {error}'

logger = logging.getLogger(__name__)


def check_tokens():
    """Проверяем доступность переменных окружения."""
    # tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    # for token in tokens:
    #     if token is None:
    #         logger.critical(NO_VARIABLE.format(token=token))
    #     raise ValueError(NO_VARIABLE.format(token=token))
    return all({PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID})


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(SUCCESSFUL_SENT_MESSAGE.format(message=message))
    except telegram.TelegramError as error:
        logger.exception(UNSUCCESSFUL_SENT_MESSAGE.format(
            message=message, error=error))


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API."""
    rq_pars = dict(
        url=ENDPOINT, headers=HEADERS, params={'from_date': timestamp})
    response = requests.get(**rq_pars)
    if response.status_code != HTTPStatus.OK:
        raise APIHTTPRequestError(API_FAILED_RESPONSE.format(
            status_code=response.status_code, **rq_pars)
        )
    try:
        return response.json()
    except requests.RequestException as error:
        raise Exception(API_FAILED_REQUEST.format(error=error, **rq_pars))


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(UNEXPECTED_TYPE_DICT.format(type=type(response)))
    if 'homeworks' not in response.keys():
        raise KeyError(NO_KEY.format(key='homeworks'))
    if not isinstance(response['homeworks'], list):
        raise TypeError(
            UNEXPECTED_TYPE_LIST.format(type=type(response['homeworks'])))
    return response.get('homeworks')


def parse_status(homework):
    """Возвращает статус домашней работы."""
    if 'homework_name' not in homework:
        raise ValueError(NO_KEY.format(key='homework_name'))
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(UNEXPECTED_STATUS.format(status=status))
    return STATUS_MESSAGE.format(
        homework_name=homework.get(
            'homework_name'), verdict=HOMEWORK_VERDICTS[status])


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            api_answer = get_api_answer(timestamp)
            homeworks = check_response(api_answer)
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
        except Exception as error:
            send_message(bot, ERROR_GLOBAL.format(error=error))
            logger.exception(error)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    try:
        logging.basicConfig(
            level=logging.DEBUG,
            filename=__file__ + '.log',
            format='%(asctime)s, %(funcName)s, %(levelname)s, %(message)s'
        )
        handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(handler)
        main()
    except KeyboardInterrupt as error:
        logger.exception(f'Программа была остановлена:{error}')

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
