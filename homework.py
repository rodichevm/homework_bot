import logging
import os
import sys
import time
from http import HTTPStatus

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

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}
TOKENS = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']

SUCCESSFUL_SENT_MESSAGE = 'Сообщение {message} успешно отправлено'
UNSUCCESSFUL_SENT_MESSAGE = (
    'Не удалось отправить сообщение "{message}. Ошибка:{error}"')
STATUS_MESSAGE = 'Изменился статус проверки работы "{homework_name}".{verdict}'
UNEXPECTED_STATUS = 'Неожиданный статус домашней работы:"{status}"'
UNEXPECTED_TYPE_LIST_HOMEWORKS = (
    'Ответ API вернул не список по ключу "homeworks", а вернул тип: {type}')
UNEXPECTED_TYPE_DICT = 'Ответ API вернул не словарь, а вернул тип: {type}'
UNEXPECTED_API_RESPONSE = (
    'Ответ API не соответствует документации({response}).{error}')
API_FAILED_RESPONSE = (
    'Эндпоинт API {ENDPOINT} недоступен. Код ответа API: {status_code}. '
    'Header: {HEADERS}. Kлюч: {key}. Значение ключа: {value}'
)
API_FAILED_REQUEST = (
    'Ошибка запроса к API:{error}, Эндпоинт API: {ENDPOINT}, '
    'Header: {HEADERS}, Timestamp: {timestamp}. Ошибка: {error}'
)
NO_KEY = 'Отсутствует ключ {key}'
NO_KEY_HOMEWORK_NAME = 'Отсутствует ключ домашней работы "homework_name"'
NO_VARIABLE = 'Отсутствует обязательная переменная окружения {token}'
ERROR_GLOBAL = 'Ошибка в работе бота: {error}'

logger = logging.getLogger(__name__)


def check_tokens():
    """Проверяем доступность переменных окружения."""
    missed_tokens = [token for token in TOKENS if not globals().get(token)]
    if missed_tokens:
        logger.critical(NO_VARIABLE.format(token=missed_tokens))
        raise ValueError(NO_VARIABLE.format(token=missed_tokens))


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(SUCCESSFUL_SENT_MESSAGE.format(message=message))
        return True
    except telegram.TelegramError as error:
        logger.exception(UNSUCCESSFUL_SENT_MESSAGE.format(
            message=message, error=error))
        return False


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API."""
    request_params = dict(
        url=ENDPOINT, headers=HEADERS, params={'from_date': timestamp})
    try:
        response = requests.get(**request_params)
    except requests.RequestException as error:
        raise ConnectionError(
            API_FAILED_REQUEST.format(error=error, **request_params))
    if response.status_code != HTTPStatus.OK:
        raise ValueError(API_FAILED_RESPONSE.format(
            status_code=response.status_code, **request_params)
        )
    api_response = response.json()
    for key in ['code', 'error']:
        if key in api_response:
            raise ValueError(
                API_FAILED_RESPONSE.format(
                    key=key, value=api_response.get(key), **request_params))
    return api_response


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(UNEXPECTED_TYPE_DICT.format(type=type(response)))
    if 'homeworks' not in response:
        raise KeyError(NO_KEY.format(key='homeworks'))
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError(
            UNEXPECTED_TYPE_LIST_HOMEWORKS.format(type=type(homeworks)))
    return homeworks


def parse_status(homework):
    """Возвращает статус домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError(NO_KEY_HOMEWORK_NAME)
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
    previous_message = ''
    message = ''
    while True:
        try:
            api_answer = get_api_answer(timestamp)
            homeworks = check_response(api_answer)
            if homeworks:
                message = parse_status(homeworks[0])
            if previous_message != message and send_message(bot, message):
                previous_message = message
                timestamp = api_answer.get('current_date', timestamp)
        except Exception as error:
            message = ERROR_GLOBAL.format(error=error)
            logging.exception(ERROR_GLOBAL.format(error=error))
            if message != previous_message and send_message(bot, message):
                previous_message = message
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    try:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s, %(funcName)s, %(levelname)s, %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(__file__ + '.log', mode='w')])
        main()
    except KeyboardInterrupt as error:
        logger.exception(f'Программа была остановлена:{error}')
    # for testing
    # from unittest import TestCase, mock, main as uni_main
    # JSON = {'error': 'testing'}
    # JSON = {'homeworks': [{'homework_name': 'test', 'status': 'approved'}]}
    # class TestReq(TestCase):
    #     @mock.patch('requests.get')
    #     def test_error(self, rq_get):
    #         resp = mock.Mock()
    #         resp.json = mock.Mock(return_value=JSON)
    #         rq_get.return_value = resp
    #         main()
    # uni_main()
