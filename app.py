from flask import Flask, request

import logging

import json

from swift import words

import random, time, math

import requests

import sqlite3


app = Flask(__name__)

logging.basicConfig(level=logging.INFO, filename='logging.log',
    format='%(asctime)s %(levelname)s %(name)s %(message)s')

logging.warning('start')


class DB:
    def __init__(self):
        conn = sqlite3.connect('records.db', check_same_thread=False)
        self.conn = conn

    def get_connection(self):
        return self.conn

    def __del__(self):
        self.conn.close()


class UsersModel:
    def __init__(self, connection):
        self.connection = connection

    def init_table(self):
        cursor = self.connection.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users
                                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                                 user_name VARCHAR(50),
                                 record INTEGER
                                 )''')
        cursor.close()

        self.connection.commit()

    def insert(self, user_name, record):
        cursor = self.connection.cursor()
        cursor.execute('''INSERT INTO users
                          (user_name, record)
                          VALUES (?,?)''', (user_name, record))
        cursor.close()

        self.connection.commit()

    def get(self, user_id):
        cursor = self.connection.cursor()
        if user_id == 'all':
            cursor.execute("SELECT * FROM users")
            row = cursor.fetchall()
        else:
            cursor.execute("SELECT * FROM users WHERE id = ?", [str(user_id)])
            row = cursor.fetchone()

        return row

    def get_by_name(self, name):
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE user_name = ?", [name])
        row = cursor.fetchone()

        return row

    def correct_user(self, user_name, password_hash):
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE user_name = ? AND password_hash = ?",
                       (user_name, password_hash))
        row = cursor.fetchone()

        return (True, row[0]) if row else (False,)

    def update_rec(self, name, record):
        cursor = self.connection.cursor()
        logging.warning('{}, {} TRYING'.format(name, record))
        cursor.execute('''UPDATE users
                          SET record = ?
                          WHERE user_name = ?''', (record, name))
        logging.warning('GOT IT')
        cursor.close()
        self.connection.commit()

    def check_username(self, user_name):
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE user_name = ?", [user_name])
        row = cursor.fetchone()
        if row :
            return (True, row[0])
        else:
            return False


def decor(lvl):
    sentence = ' '.join([random.choice(words) for i in range(lvl // 3 + 1)])
    times = len(sentence) / 2.4 + 4

    return sentence, times


@app.route('/post', methods=['POST'])
def main():

    logging.info('Request: %r', request.json)

    response = {
        'session': request.json['session'],
        'version': request.json['version'],
        'response': {
            'end_session': False
        }
    }

    handle_dialog(response, request.json)

    logging.info('Request: %r', response)

    return json.dumps(response)


pict = ['.', ',']
words = list(filter(lambda x: x not in pict, words))




db = DB()
user_model = UsersModel(db.get_connection())
user_model.init_table()


sessionStorage = {}
game_params = {}


def handle_dialog(res, req):
    user_id = req['session']['user_id']

    if req['session']['new']:

        res['response']['text'] = 'Привет! Назови свое имя!'
        sessionStorage[user_id] = {
            'first_name': None
        }
        game_params['active_game'] = False
        game_params['scores'] = 0
        game_params['lives'] = 2
        game_params['inrow'] = 0
        game_params['level'] = 1
        return

    cities = get_cities(req)

    if sessionStorage[user_id]['first_name'] is None:
        # в последнем его сообщение ищем имя.
        first_name = get_first_name(req)
        # если не нашли, то сообщаем пользователю что не расслышали.
        if first_name is None:
            res['response']['text'] = \
                'Не расслышала имя. Повтори, пожалуйста!'
            return
        elif len(first_name) > 50:
            res['response']['text'] = \
                'Имя содержит больше 50 символов'
        else:
            if user_model.check_username(first_name):
                res['response']['text'] = 'С возвращением {}'.format(first_name)
                sessionStorage[user_id]['first_name'] = first_name
            else:
                user_model.insert(first_name.lower(), 0)
                sessionStorage[user_id]['first_name'] = \
                first_name
                res['response'][
                    'text'] = 'Приятно познакомиться, ' \
                    + user_model.get_by_name(first_name)[1].title() \
                              + '. Я - Алиса. Я могу проверить тебя на скорость печати!'

            suggests = []
            suggests.append({'title': 'start', 'hide': True})
            suggests.append({'title': 'top', 'hide': True})
            suggests.append({'title': 'name record', 'hide': True})
            suggests.append({'title': 'помощь', 'hide': True})
            res['response']['buttons'] = suggests
        return
    command = req['request']['command'].split()

    if game_params['active_game'] == 'namerecord':
        user = user_model.get_by_name(''.join(command).lower())
        if user:
            res['response']['text'] = '{} - {} очков'.format(user[1], user[2])
            game_params['active_game'] = False
            suggests = []
            suggests.append({'title': 'start', 'hide': True})
            suggests.append({'title': 'top', 'hide': True})
            suggests.append({'title': 'name record', 'hide': True})
            suggests.append({'title': 'помощь', 'hide': True})
            res['response']['buttons'] = suggests
            return
        elif ''.join(command).lower() in\
                [
                    'забей',
                    'stop',
                    'хватит',
                    'нетоимя',
                    'стоп',
                    'остановись',
                    'все'
                ]:
            game_params['active_game'] = False
            res['response']['text'] = 'Ok!'
            suggests = []
            suggests.append({'title': 'start', 'hide': True})
            suggests.append({'title': 'top', 'hide': True})
            suggests.append({'title': 'name record', 'hide': True})
            suggests.append({'title': 'помощь', 'hide': True})
            res['response']['buttons'] = suggests
            return
        else:
            res['response']['text'] = \
                'Такого у нас нет! Поищите других или скажите "забей"'
            suggests = []
            suggests.append({'title': 'не то имя', 'hide': True})
            res['response']['buttons'] = suggests
            return

    if game_params['active_game'] == 'pause':
        if ''.join(command).lower() in\
                [
            'go',
            'го',
            'погнали',
            "продолжаем",
            "вперед"
                ]:
            game_params['active_game'] = True
            return_word(res)
            suggests = []
            suggests.append({'title': 'пауза', 'hide': True})
            res['response']['buttons'] = suggests
            return
        elif ''.join(command).lower() in\
                [
            'stats',
            'stata',
            "стата",
            "статистика",
            "очки"
                ]:
            text_to_send = ''
            text_to_send += 'Очков:{}'.format(game_params['scores'])
            text_to_send += '\nУровень:{}'.format(game_params['level'])
            text_to_send += '\nПодряд:{}'.format(game_params['inrow'])
            text_to_send += '\nЖизней:{}\n'.format(game_params['lives'])
            text_to_send += '\n'
            res['response']['text'] = text_to_send
            suggests = []
            suggests.append({'title': 'го', 'hide': True})
            suggests.append({'title': 'все', 'hide': True})
            suggests.append({'title': 'статистика', 'hide': True})
            res['response']['buttons'] = suggests
            return
        elif ''.join(command).lower() in\
                [
            "все",
            "хватит",
            "наигрался",
            "конец",
            "стопигра"
                ]:
            text_to_send = ''
            text_to_send += '\nКонец игры. Cчет - {}\n'.\
                format(game_params['scores'])
            game_params['active_game'] = False

            host = user_model.get_by_name(sessionStorage[user_id]['first_name'])
            if host[2] != 0:
                if host[2] < game_params['scores']:
                    text_to_send += '\nУ вас новый рекорд!'
                    user_model.update_rec(host[1], game_params['scores'])
            else:
                text_to_send += '\nВаш первый рекорд!'
                user_model.update_rec(host[1], game_params['scores'])
            res['response']['text'] = text_to_send
            suggests = []
            suggests.append({'title': 'start', 'hide': True})
            suggests.append({'title': 'top', 'hide': True})
            suggests.append({'title': 'name record', 'hide': True})
            suggests.append({'title': 'помощь', 'hide': True})
            res['response']['buttons'] = suggests
            return
        else:
            res['response']['text'] = 'Ну что? Так и будешь отдыхать?'
            suggests = []
            suggests.append({'title': 'го', 'hide': True})
            suggests.append({'title': 'все', 'hide': True})
            suggests.append({'title': 'статистика', 'hide': True})
            res['response']['buttons'] = suggests
            return

    if not game_params['active_game']:
        if ''.join(command).lower() == 'start':
            game_params['scores'] = 0
            game_params['lives'] = 2
            game_params['inrow'] = 0
            game_params['level'] = 1
            game_params['active_game'] = True
            suggests = []
            suggests.append({'title': 'пауза', 'hide': True})
            res['response']['buttons'] = suggests
            return_word(res)
        elif ''.join(command).lower() == 'top':
            top = sorted(user_model.get('all'), key=lambda x: -x[2])
            endd = 10 if len(top) > 10 else len(top)
            text_to_send = ''
            for i in top[:endd]:
                text_to_send += '{} - {} очков\n'.format(i[1], i[2])
            res['response']['text'] = text_to_send
            suggests = []
            suggests.append({'title': 'start', 'hide': True})
            suggests.append({'title': 'top', 'hide': True})
            suggests.append({'title': 'name record', 'hide': True})
            suggests.append({'title': 'помощь', 'hide': True})
            res['response']['buttons'] = suggests
            return
        elif ''.join(command).lower() == 'namerecord':
            res['response']['text'] = 'Введите имя рекордсмена'
            game_params['active_game'] = 'namerecord'
            suggests = []
            suggests.append({'title': 'забей', 'hide': True})
            res['response']['buttons'] = suggests
            return
        elif ''.join(command).lower() == 'помощь':
            res['response']['text'] = 'После того как вы ввели имя, у вас есть несоклько опций: \n' \
                                      '1. start - начать игру,' \
                                      ' очки в которой начисляются в зависимости от:\n' \
                                      '\t1) Быстроты ответа\n' \
                                      '\t2) Того, насколько велика серия верных ответов\n' \
                                      '\t3) Уровня, на котором вы находитесь\n' \
                                      '2. top - выводит топ 10 игроков\n' \
                                      '3. name record - после введения этой команды нужно написать' \
                                      'имя человека, рекорд которого вы хотите узнать'
            suggests = []
            suggests.append({'title': 'start', 'hide': True})
            suggests.append({'title': 'top', 'hide': True})
            suggests.append({'title': 'name record', 'hide': True})
            suggests.append({'title': 'помощь', 'hide': True})
            res['response']['buttons'] = suggests
        else:
            res['response']['text'] = 'Такой команды нет' \
                                      '\nstart - начало игры' \
                                      '\ntop - лидеры' \
                                      '\nname record - рекорд игрока'
            suggests = []
            suggests.append({'title': 'start', 'hide': True})
            suggests.append({'title': 'top', 'hide': True})
            suggests.append({'title': 'name record', 'hide': True})
            suggests.append({'title': 'помощь', 'hide': True})
            res['response']['buttons'] = suggests

    else:
        if ''.join(command).lower() in\
                [
            'стоп',
            'stop',
            'stata',
            'стата',
            'статистика',
            'pause',
            'пауза'
                ]:
            text_to_send = ''
            text_to_send += 'Очков:{}'.format(game_params['scores'])
            text_to_send += '\nУровень:{}'.format(game_params['level'])
            text_to_send += '\nПодряд:{}'.format(game_params['inrow'])
            text_to_send += '\nЖизней:{}\n'.format(game_params['lives'])
            game_params['active_game'] = 'pause'
            res['response']['text'] = text_to_send
            game_params['inrow'] = 0
            suggests = []
            suggests.append({'title': 'го', 'hide': True})
            suggests.append({'title': 'все', 'hide': True})
            suggests.append({'title': 'статистика', 'hide': True})
            res['response']['buttons'] = suggests
            return
        text_to_send = ''
        game_params['time2'] = time.time()
        differ = game_params['time2'] - game_params['time1']
        lizd = []
        if ' '.join(command).lower() != game_params['sent'].lower():
            game_params['lives'] -= 1
            game_params['inrow'] = 0
            lizd.append('ошибка в написании')
            lizd.append('Очков:{}\nУровень:{}\nПодряд:{}\nЖизней:{}'.format(
                game_params['scores'], game_params['level'],
                game_params['inrow'], game_params['lives']))
            suggests = []
            suggests.append({'title': 'пауза', 'hide': True})
            res['response']['buttons'] = suggests
        elif differ > game_params['maxtime']:
            game_params['lives'] -= 1
            game_params['inrow'] = 0
            lizd.append('вышло время')
            lizd.append('Очков:{}\nУровень:{}\nПодряд:{}\nЖизней:{}'.format(
                game_params['scores'], game_params['level'],
                game_params['inrow'], game_params['lives']))
            suggests = []
            suggests.append({'title': 'пауза', 'hide': True})
            res['response']['buttons'] = suggests
        else:
            game_params['inrow'] += 1
            game_params['level'] += 1
            game_params['scores'] += int(len(game_params['sent']) * (
                game_params['maxtime'] - differ) * (game_params['inrow'] * 0.5))
            suggests = []
            suggests.append({'title': 'пауза', 'hide': True})
            res['response']['buttons'] = suggests

        if game_params['lives'] <= 0:
            # res['response']['text'] = 'КОНЕЦ.....\n{}\n'.format(game_params['lives'])
            # return
            text_to_send = ''
            text_to_send += '\nУ вас закончились жизни. Cчет - {}\n'.\
                format(game_params['scores'])
            game_params['active_game'] = False

            host = user_model.get_by_name(sessionStorage[user_id]['first_name'])
            if host[2] != 0:
                if host[2] < game_params['scores']:
                    text_to_send += '\nУ вас новый рекорд!'
                    user_model.update_rec(host[1], game_params['scores'])
            else:
                text_to_send += '\nВаш первый рекорд!'
                user_model.update_rec(host[1], game_params['scores'])
            res['response']['text'] = text_to_send
            suggests = []
            suggests.append({'title': 'start', 'hide': True})
            suggests.append({'title': 'top', 'hide': True})
            suggests.append({'title': 'name record', 'hide': True})
            suggests.append({'title': 'помощь', 'hide': True})
            res['response']['buttons'] = suggests
            return

        if game_params['inrow'] % 10 == 0 and game_params['inrow'] != 0:
            game_params['lives'] += 1
            game_params['level'] -= 1
            res['response']['text'] = 'Очков:{}\nУровень:{}\nПодряд:{}\nЖизней:{}'.format(
            game_params['scores'], game_params['level'], game_params['inrow'], game_params['lives'])
        return_word(res, lizd)


def return_word(res, lizd=[]):
    #time.sleep(0.5)
    sent, maxtime = decor(game_params['level'])
    text_to_send = ''
    for i in lizd:
        text_to_send += '{}\n'.format(i)
    text_to_send += '\n'
    text_to_send += sent
    res['response']['text'] = text_to_send
    game_params['sent'] = sent
    game_params['time1'] = time.time()
    game_params['maxtime'] = maxtime
    return


def get_first_name(req):
    # перебираем сущности
    for entity in req['request']['nlu']['entities']:
        # находим сущность с типом 'YANDEX.FIO'
        if entity['type'] == 'YANDEX.FIO':
            # Если есть сущность с ключом 'first_name',
            # то возвращаем ее значение.
            # Во всех остальных случаях возвращаем None.
            return entity['value'].get('first_name', None)


def get_cities(req):

    cities = []

    for entity in req['request']['nlu']['entities']:

        if entity['type'] == 'YANDEX.GEO':

            if 'city' in entity['value'].keys():
                cities.append(entity['value']['city'])

    return cities


if __name__ == '__main__':
    app.run()
