import os
import time
from pprint import pprint

import requests

from dotenv import load_dotenv
from telegram import Bot

from exceptions import NoneValueConstant


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


def check_tokens():
    """Проверяем доступность переменных окружения"""
    variables = [
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID
    ]
    for var in variables:
        if not var:
            raise ValueError(f'Переменная окружения отсутствует')


def send_message(bot, message):
    bot.send_message(TELEGRAM_CHAT_ID, message)


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API"""
    url = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
    headers = {
        'Authorization':
            'OAuth y0_AgAAAAATLXDEAAYckQAAAADdV8XB8UDO36cbSkmAX6Q6DHL1K7KoCdM'}
    payload = {'from_date': timestamp - 2592000}
    homeworks = requests.get(url, headers=headers, params=payload)
    return homeworks.json()


def check_response(response):
    if response['homeworks']:
        return True


def parse_status(status):
    homework_name = status['lesson_name']
    verdict = HOMEWORK_VERDICTS[status['status']]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""

    check_tokens()
    bot = Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    api_answer = get_api_answer(timestamp)

    check_response(api_answer)

    while True:
        try:
            homework = api_answer['homeworks'][0]
            status = homework['status']
            message = parse_status(status)
            send_message(bot, message)

            ...

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            # send_message(bot, message)


if __name__ == '__main__':
    main()
