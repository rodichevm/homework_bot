import os
import logging
import sys
import time
from http import HTTPStatus

import requests

from dotenv import load_dotenv
from telegram import Bot

from exceptions import APIHTTPRequestError

load_dotenv()

logging.basicConfig(level=logging.INFO)

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
    return PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат"""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception:
        return 'Не удалось отправить сообщение'


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API"""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp - 2592000}
        )
        status_code = response.status_code
        if status_code == HTTPStatus.OK:
            return response.json()
        else:
            return f'Код ответа {status_code}. API недоступен'
    except APIHTTPRequestError:
        return 'Ошибка при запросе к API'


def check_response(response):
    """Проверяет ответ API на соответствие документации"""
    if type(response) is not dict:
        raise TypeError
    if response.keys() == {'homeworks', 'current_date'}:
        if type(response['homeworks']) is not list:
            raise TypeError
        return response.get('homeworks')
    else:
        raise KeyError


def parse_status(homework):
    """Возвращает статус домашней работы"""
    homework_name = homework.get('lesson_name')
    verdict = HOMEWORK_VERDICTS[homework.get('status')]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if check_tokens() is False:
        sys.exit()
    bot = Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            api_answer = get_api_answer(timestamp)
            homeworks = check_response(api_answer)
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
            else:
                return 'нет обновлений'
            timestamp_current = homeworks.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
