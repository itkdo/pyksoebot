from telebot import apihelper, types, TeleBot
from datetime import datetime
import time
from threading import Thread
import cherrypy
import requests
import schedule
import re
from enum import Enum

from bs4 import BeautifulSoup
import config


class WebhookServer(object):
    def __init__(self, bot: TeleBot) -> None:
        super().__init__()
        self.bot = bot


    @cherrypy.expose
    def index(self):
        length = int(cherrypy.request.headers['content-length'])
        json_string = cherrypy.request.body.read(length).decode("utf-8")
        update = types.Update.de_json(json_string)
        self.bot.process_new_updates([update])
        return ''


class Accident(Enum):
    AVARIA = 'avar'
    PLANNED = 'plan'


# TODO: into db
class Res(Enum):
    NovaKakhovka = 'nkres'
    GolaPrystan = 'gpres'
    Vysokopilya = 'vpres'
    Kherson = 'hges'
    Kakhovka = 'kvres'
    Novotroicke = 'ntres'
    Geninchesk = 'gnres'
    Ivanovske = 'ivres'
    VelykoLepetykha = 'vlres'
    Chaplynka = 'cpres'
    Skadovsk = 'skres'
    Oleshky = 'crres'


class KsoeBot():
    bot = TeleBot(config.BOT_TOKEN)
    cached_avar = {}
    cached_plan = {}

    def __init__(self) -> None:
        self.register_handlers()
        Thread(target=self.schedule_start, daemon=True).start()
        self.cached_avar = {"time": 0, "text": None}
        self.cached_plan = {"time": 0, "text": None}


    @staticmethod
    def render(kvargs: dict) -> str:
        return ("<b>{place}:</b>\n"
                "<code>{streets}</code>\n"
                "⚡️: <code>{reason}</code>\n"
                "⏱: <code>{times}</code>\n\n".format(**kvargs))


    @staticmethod
    def datetime_to_correct_str(date: datetime, act: Accident) -> str:
        if act == Accident.PLANNED:
            return f"{int(date.day)}.{int(date.month)}.{date.year}"
        elif act == Accident.AVARIA:
            return date.strftime('%d.%m.%Y')


    @staticmethod
    def clean_raw_html(raw_html: str) -> str:
        raw_html = str(raw_html).replace('<br/>', '\n')
        raw_html = raw_html.replace('<br><br>', "\n")
        cleanr = re.compile('<.*?>')
        cleantext = re.sub(cleanr, '', raw_html)
        return cleantext


    def get_accident_work(self, url: str, res_id: Res = Res.NovaKakhovka) -> list:
        response = requests.get(url, data={'tname': res_id.value}, headers={
            'User-agent': 'Mozilla/5.0'})

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'lxml')
            table = soup.find('table', attrs={'class': 'table-otkl'})
            table_body = table.find('tbody')

            rows = table_body.find_all('tr')
            data = {}
            cached_date = ""
            for row in rows:
                columns = row.find_all('td')
                columns = [self.clean_raw_html(col) for col in columns]
                if len(columns) == 1:
                    (cached_date,) = columns
                    cached_date = re.search("([\d\.]+)", cached_date).group(1)
                    data.setdefault(cached_date, [])
                elif len(columns) == 5:
                    data[cached_date].append(columns)
            return data
        else:
            print(response.status_code, response)
            return {}


    def format_tech_works(self, recieved_data: dict, acc_type: Accident = Accident.PLANNED) -> str:
        if acc_type == Accident.PLANNED:
            result_text = "Сьогодні немає <b>планових</b> відключень."
            acc_str = "Планові"
        else:
            result_text = 'Сьогодні немає <b>аварійних</b> відключень.'
            acc_str = "Аварійні"

        if not recieved_data:
            return result_text

        today_str = self.datetime_to_correct_str(datetime.today(), acc_type)

        if recieved_data and today_str in recieved_data.keys():
            recieved_data = recieved_data[today_str]
            filtered_data = list(filter(lambda item: len(
                [op for op in config.OBSERVABLE_PLACES if op in item[1]]) > 0, recieved_data))

            if len(filtered_data) > 0:
                result_text = f"<b>{acc_str} роботи {today_str}</b>\n\n"
                for item in filtered_data:
                    (_, streets, reason, times, _) = item

                    for el in re.findall(config.STREET_REGEX, streets):
                        pl, inf = map(str, el)
                        pl = pl.replace("\n", "")
                        streets_number = inf.replace("\n", "").split('; ')
                        temp = "\n".join([f"🔸{st}" for st in streets_number])
                        data = dict(place=pl, streets=temp,
                                    reason=reason, times=times)
                        result_text += self.render(data)
                return result_text
            else:
                return f"<b>{acc_str}</b> роботи не знайдено.\n\n"


    def broadcast(self, chat_id: int, message: str) -> None:
        if len(message) <= 4000:
            self.bot.send_message(chat_id, message, parse_mode='HTML')
        else:
            messages = message.split('\n\n')
            [self.bot.send_message(chat_id, msg, parse_mode='HTML')
             for msg in messages if msg != '']


    def shedule(self, chat_id, is_silent_pin: bool) -> None:
        now = time.time()
        if now - self.cached_plan.get("time", 0) >= 300:
            data = self.get_accident_work(config.URL_PLANNED)
            mess_plan = self.format_tech_works(data)
            self.cached_plan = {"time": now, "text": mess_plan}
        else:
            print("send cached planed works")
            mess_plan = self.cached_plan.get("text", "Нічого.")

        m = self.bot.send_message(chat_id, mess_plan, parse_mode='HTML')
        self.bot.pin_chat_message(chat_id, m.message_id, is_silent_pin)

        if now - self.cached_avar.get("time", 0) >= 300:
            data = self.get_accident_work(config.URL_ACCIDENT)
            mess_avar = self.format_tech_works(data, Accident.AVARIA)
            self.cached_avar = {"time": now, "text": mess_avar}
        else:
            print("send cached avaria works")
            mess_avar = self.cached_avar.get("text", "Нічого.")
        self.bot.send_message(chat_id, mess_avar, parse_mode='HTML')


    def schedule_start(self) -> None:
        schedule.every().day.at('07:30').do(self.shedule, -1001385768030, True)
        schedule.every().day.at('08:15').do(self.shedule, config.rubinchat, True)
        schedule.every().day.at('13:15').do(self.shedule, config.rubinchat, True)
        while True:
            schedule.run_pending()
            time.sleep(1)


    def __add_message_handler(self, handler, commands=None, func=None, regexp=None, content_types=None) -> None:
        self.bot.add_message_handler(self.bot._build_handler_dict(
            handler, content_types=content_types, commands=commands, func=func, regexp=regexp))


    def register_handlers(self) -> None:
        self.__add_message_handler(self.start_handler, commands=["start"])
        self.__add_message_handler(self.id_handler, commands=["id"])
        self.__add_message_handler(self.planned_handler, commands=["planned"])
        self.__add_message_handler(self.accident_handler, commands=["avaria"])
        self.__add_message_handler(self.help_handler, commands=["help"])


    @classmethod
    def start_handler(cls, message):
        cls.bot.send_message(
            message.chat.id, ("Привіт! Я бот для перевірки стану ремонтних робіт електромереж у Херсонській області.\n"
                              "Тисни /help, щоб дізнатися що я вмію."))


    @classmethod
    def id_handler(cls, message):
        if message.reply_to_message:
            cls.bot.send_message(
                message.chat.id, f"{message.reply_to_message.from_user.id}")
        else:
            cls.bot.send_message(message.chat.id, f"{message.chat.id}")

        if message.from_user.id != message.chat.id:
            try:
                cls.bot.delete_message(
                    chat_id=message.chat.id, message_id=message.message_id)
            except apihelper.ApiException:
                pass


    @classmethod
    def planned_handler(cls, message):
        if message.from_user.id != message.chat.id:
            cls.bot.delete_message(message.chat.id, message.message_id)
        now = time.time()
        if now - cls.cached_plan.get("time", 0) >= 300:
            data = cls.get_accident_work(cls, url=config.URL_PLANNED)
            mess_plan = cls.format_tech_works(cls, data, Accident.PLANNED)
            cls.cached_plan = {"time": now, "text": mess_plan}
        else:
            print("send cached planed works")
            mess_plan = cls.cached_plan.get("text", "Нічого.")

        cls.broadcast(cls, message.chat.id, mess_plan)


    @classmethod
    def accident_handler(cls, message):
        if message.from_user.id != message.chat.id:
            cls.bot.delete_message(message.chat.id, message.message_id)
        now = time.time()
        print(cls.cached_avar)
        if now - cls.cached_avar.get("time", 0) >= 300:
            data = cls.get_accident_work(cls, config.URL_ACCIDENT)
            mess_avar = cls.format_tech_works(cls, data, Accident.AVARIA)
            cls.cached_avar = {"time": now, "text": mess_avar}
        else:
            print("send cached avaria works")
            mess_avar = cls.cached_avar.get("text", "Нічого.")

        cls.broadcast(cls, message.chat.id, mess_avar)

    @classmethod
    def help_handler(cls, message):
        mess = ("/planned - Перевірити планові роботи\n"
                "/avaria - Перевірити аварійні відключення\n\n"
                "Інформація представлена сайтом https://ksoe.com.ua/\n"
                "⚠️ Дані відображаються поки що тільки для таких населенних пунктів:\n" +
                ", ".join([f"<b>{i}</b>" for i in config.OBSERVABLE_PLACES]) +
                f"\n\n🤖За пропозиціями і побажаннями щодо покращення роботи бота - звертатися до <a href='tg://user?id={config.admin}'>мого розробника</a>")
        cls.bot.send_message(message.chat.id, mess,
                             parse_mode='HTML', disable_web_page_preview=True)

    def run(self):
        try:
            print(f"{datetime.now().strftime('%d.%m.%Y %H:%M:%S')} - Bot start")
            self.bot.delete_webhook()
            self.bot.set_webhook(url=config.WEBHOOK_URL)

            cherrypy.config.update({
                'server.socket_host': '127.0.0.1',
                'server.socket_port': config.WEBHOOK_PORT,
                'engine.autoreload.on': True})

            cherrypy.quickstart(WebhookServer(self.bot), '/', {'/': {}})
        except apihelper.ApiException:
            print(
                f"{datetime.now().strftime('%d.%m.%Y %H:%M:%S')} - Fail set webhook. Start with pollig")
            self.bot.delete_webhook()
            self.bot.polling(none_stop=True, interval=1, timeout=400000)


if __name__ == '__main__':
    KsoeBot().run()
