import datetime
import requests
import config
import telebot
import time
from bs4 import BeautifulSoup
from collections import Counter

bot = telebot.TeleBot(config.access_token)

response =\
    requests.get('http://www.ifmo.ru/ru//schedule/raspisanie_zanyatiy.htm') #находим список групп по тэгу, если вводишь чушь, то выдает false
soup = BeautifulSoup(response.text, "html5lib")
groups = soup.find("div", attrs={"id": "content"})
groups_list = groups.find_all("a")
groups_list = [group_number.text for group_number in groups_list]


def get_page(group, week=''):
    if week:
        week = str(week) + '/'
    url = '{domain}/{group}/{week}raspisanie_zanyatiy_{group}.htm'.format(
        domain=config.domain,
        week=week,
        group=group)
    response = requests.get(url)
    web_page = response.text
    return web_page


def parse_schedule_for_anyday(web_page, day):
    soup = BeautifulSoup(web_page, "html5lib")

    if day == '/monday' or day == '/sunday':
        schedule_table = soup.find("table", attrs={"id": "1day"})
    elif day == '/tuesday':
        schedule_table = soup.find("table", attrs={"id": "2day"})
    elif day == '/wednesday':
        schedule_table = soup.find("table", attrs={"id": "3day"})
    elif day == '/thursday':
        schedule_table = soup.find("table", attrs={"id": "4day"})
    elif day == '/friday':
        schedule_table = soup.find("table", attrs={"id": "5day"})
    elif day == '/saturday':
        schedule_table = soup.find("table", attrs={"id": "6day"})
    if schedule_table is not None:

        times_list = schedule_table.find_all("td", attrs={"class": "time"})
        times_list = [time.span.text for time in times_list]

        locations_list = schedule_table.find_all("td", attrs={"class": "room"})
        locations_list = [room.span.text for room in locations_list]

        lessons_list = schedule_table.find_all("td", attrs={"class": "lesson"})
        lessons_list = [lesson.text.split('\n\n') for lesson in lessons_list]
        lessons_list = [', '.join([info for info in lesson_info if info])
                        for lesson_info in lessons_list]
        for num_element in range(len(lessons_list)):
            lessons_list[num_element] =\
                lessons_list[num_element].replace('\n', '').replace('\t', '') #зареплейсили табулящию и переход на новую строку тоже

        classrooms_list = schedule_table.find_all("td",
                                                  attrs={"class": "room"})
        classrooms_list = [classroom.dd.text for classroom in classrooms_list]

        notes_list = schedule_table.find_all("td", attrs={"class": "time"}) #вывод по красоте (четная или нечетная неделя)
        notes_list = [note.dt.text for note in notes_list]

        return times_list, notes_list, locations_list, lessons_list,\
            classrooms_list
    else:
        return 0


def is_valid(group):
    if group in groups_list:
        return True
    else:
        return False


@bot.message_handler(commands=['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'])
def get_schedule(message):
    whitespaces = message.text.count(' ')
    if whitespaces != 2:
        return None
    day, week, group = message.text.split()
    if is_valid(group):
        web_page = get_page(group, week) 
        group_schedule = parse_schedule_for_anyday(web_page, day)
        if group_schedule == 0:
            resp = '<b>Ты свободен</b>'
        else:
            times_lst, notes_lst, locations_lst, lessons_lst, classrooms_lst =\
                    group_schedule
            resp = ''
            for time, note, location, lesson, classroom\
                    in zip(times_lst,
                           notes_lst,
                           locations_lst,
                           lessons_lst,
                           classrooms_lst):
                resp += '<b>{}</b>, <i>{}</i> {}, {}, {}\n'\
                    .format(time, note, location, lesson, classroom)
    else:
        resp = 'Такой группы не существует'
    bot.send_message(message.chat.id, resp, parse_mode='HTML')


def get_near_next_day_lesson(web_page, group, week, today):
    days_of_week = ['/monday',
                    '/tuesday',
                    '/wednesday',
                    '/thursday',
                    '/friday',
                    '/saturday']
    if today == 6:
        if week == 2:
            week = 1
        else:
            week = 2
        today = 0
        web_page = get_page(group, week)

    group_schedule = parse_schedule_for_anyday(web_page, days_of_week[today])
    while group_schedule == 0:
        today += 1
        if today == 6:
            if week == 2:
                week = 1
            else:
                week = 2
            today = 0
            web_page = get_page(group, week)

    group_schedule = parse_schedule_for_anyday(web_page, days_of_week[today])
    times_lst, notes_lst, locations_lst, lessons_lst, classrooms_lst = \
        group_schedule

    resp = '<b>{}</b>, <i>{}</i> {}, {}, {}\n'.format(times_lst[0],
                                                      notes_lst[0],
                                                      locations_lst[0],
                                                      lessons_lst[0],
                                                      classrooms_lst[0])
    return resp


@bot.message_handler(commands=['near'])
def get_near_lesson(message):
    whitespaces = message.text.count(' ')
    if whitespaces != 1:
        return None
    _, group = message.text.split()
    if int(datetime.datetime.today().strftime('%W')) % 2 == 0:
        week = 1
    else:
        week = 2
    today = datetime.datetime.now().weekday()
    days_of_week = ['/monday',
                    '/tuesday',
                    '/wednesday',
                    '/thursday',
                    '/friday',
                    '/saturday']
    if is_valid(group):
        web_page = get_page(group, week)
        group_schedule = parse_schedule_for_anyday(web_page,
                                                   days_of_week[today])
        if group_schedule:
            times_lst, notes_lst, locations_lst, lessons_lst,\
                    classrooms_lst = group_schedule
            for num_lesson in range(len(times_lst)):
                if times_lst[num_lesson] != 'День':
                    _, time = times_lst[num_lesson].split('-')
                    time_hour, time_minute = time.split(':')
                    time = int(time_hour + time_minute)
                no_time = Counter(times_lst)
                if no_time['День'] == len(times_lst):
                    today += 1
                    resp = get_near_next_day_lesson(web_page,
                                                    group,
                                                    week,
                                                    today)
                    bot.send_message(message.chat.id, resp, parse_mode='HTML')
                    break
                current_time = int(str(datetime.datetime.now().hour) +
                                   str(datetime.datetime.now().minute))
                if current_time < time:
                    resp = '<b>{}</b>, <i>{}</i> {}, {}, {}\n'\
                            .format(times_lst[num_lesson],
                                    notes_lst[num_lesson],
                                    locations_lst[num_lesson],
                                    lessons_lst[num_lesson],
                                    classrooms_lst[num_lesson])
                    bot.send_message(message.chat.id, resp, parse_mode='HTML')
                    break
                if num_lesson == len(times_lst) - 1:
                    today += 1
                    resp = get_near_next_day_lesson(web_page,
                                                    group,
                                                    week,
                                                    today)
                    bot.send_message(message.chat.id, resp, parse_mode='HTML')
        else:
            resp = get_near_next_day_lesson(web_page, group, week, today)
            bot.send_message(message.chat.id, resp, parse_mode='HTML')
    else:
        resp = 'Вы ввели неверный номер группы'
        bot.send_message(message.chat.id, resp, parse_mode='HTML')


@bot.message_handler(commands=['tommorow'])
def get_tommorow(message):
    """ Получить расписание на следующий день """
    whitespaces = message.text.count(' ')
    if whitespaces != 1:
        return None
    _, group = message.text.split()
    if int(datetime.datetime.today().strftime('%W')) % 2 == 0:
        week = 1
    else:
        week = 2
    today = datetime.datetime.now().isoweekday()

    if today == 1:
        next_day = '/tuesday'
    if today == 2:
        next_day = '/wednesday'
    if today == 3:
        next_day = '/thursday'
    if today == 4:
        next_day = '/friday'
    if today == 5:
        next_day = '/saturday'
    if today == 6 or today == 7:
        next_day = '/monday'
        if week == 2:
            week = 1
        else:
            week = 2

    if is_valid(group):
        web_page = get_page(group, week)
        group_schedule = parse_schedule_for_anyday(web_page, next_day)
        if group_schedule == 0:
            resp = '<b>В этот день нет занятий</b>'
        else:
            times_lst, notes_lst, locations_lst, lessons_lst,\
                    classrooms_lst = group_schedule
            resp = ''
            for time, note, location, lesson, classroom in\
                    zip(times_lst,
                        notes_lst,
                        locations_lst,
                        lessons_lst,
                        classrooms_lst):
                resp += '<b>{}</b>, <i>{}</i> {}, {}, {}\n'\
                    .format(time, note, location, lesson, classroom)
    else:
        resp = 'Такой группы не существует'
    bot.send_message(message.chat.id, resp, parse_mode='HTML')


@bot.message_handler(commands=['all'])
def get_all_schedule(message):
    whitespaces = message.text.count(' ')
    if whitespaces != 2:
        return None
    _, week, group = message.text.split()
    if week == '0':
        week = ''
    resp = ''
    days_of_week = ['/monday',
                    '/tuesday',
                    '/wednesday',
                    '/thursday',
                    '/friday',
                    '/saturday']
    translation = ['Понедельник',
                   'Вторник',
                   'Среда',
                   'Четверг!',
                   'Пятница',
                   'Суббота']

    if is_valid(group):
        web_page = get_page(group, week)
        for num_day in range(len(days_of_week)):
            resp += '<b>' + translation[num_day] + '</b>\n\n'
            day = days_of_week[num_day]
            group_schedule = parse_schedule_for_anyday(web_page, day)
            if group_schedule == 0:
                resp += '<b>Ты свободен</b>\n\n'
            else:
                times_lst, notes_lst, locations_lst, lessons_lst,\
                    classrooms_lst = group_schedule
                for time, note, location, lesson, classroom \
                        in zip(times_lst,
                               notes_lst,
                               locations_lst,
                               lessons_lst,
                               classrooms_lst):
                    resp += '<b>{}</b>, <i>{}</i> {}, {}, {}\n'\
                        .format(time,
                                note,
                                location,
                                lesson,
                                classroom)
                resp += '\n'
    else:
        resp = 'Такой группы не существует'
    bot.send_message(message.chat.id, resp, parse_mode='HTML')

if __name__ == '__main__':
    bot.polling(none_stop=True)
