from telebot import apihelper, types, TeleBot
from datetime import datetime
import time
from threading import Thread
import cherrypy
import requests
import schedule
import re

from bs4 import BeautifulSoup
import config


class WebhookServer(object):
    def __init__(self, bot:TeleBot) -> None:
        super().__init__()
        self.bot = bot

    @cherrypy.expose
    def index(self):
        length = int(cherrypy.request.headers['content-length'])
        json_string = cherrypy.request.body.read(length).decode("utf-8")
        update = types.Update.de_json(json_string)
        self.bot.process_new_updates([update])
        return ''


class KsoeBot():
    bot = TeleBot(config.BOT_TOKEN)

    def __init__(self) -> None:
        self.register_handlers()
        Thread(target=self.schedule_start, daemon=True).start()

    @staticmethod
    def render(kvargs: dict) -> str:
        return("<b>{place}:</b>\n"
               "<code>{streets}</code>\n"
               "⚡️: <code>{reason}</code>\n"
               "⏱: <code>{times}</code>\n\n".format(**kvargs))

    @staticmethod
    def get_date_string(date: datetime, act: str) -> str:
        if act == 'plan':
            return f"{int(date.day)}.{int(date.month)}.{date.year}"
        elif act == 'avar':
            return date.strftime('%d.%m.%Y')

    @staticmethod
    def clean_raw_html(raw_html: str) -> str:
        raw_html = str(raw_html).replace('<br/>', '\n')
        raw_html = raw_html.replace('<br><br>', "\n")
        cleanr = re.compile('<.*?>')
        cleantext = re.sub(cleanr, '', raw_html)
        return cleantext

    def get_accident_work(self, url: str, res_id="nkres") -> list:
        response = requests.get(url, data={'tname': res_id}, headers={
            'User-agent': 'Mozilla/5.0'})

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'lxml')
            table = soup.find('table', attrs={'class': 'table-otkl'})
            table_body = table.find('tbody')

            rows = table_body.find_all('tr')
            data = []
            for row in rows:
                columns = row.find_all('td')
                columns = [self.clean_raw_html(col) for col in columns]
                data.append([col for col in columns if col])
            return data
        else:
            return []

    # TODO: More refactor to this

    def format_tech_works(self, recieved_data: list, is_planned=True) -> str:
        if is_planned:
            result_text = "Сьогодні немає <b>планових</b> відключень."
        else:
            result_text = 'Сьогодні немає <b>аварійних</b> відключень.'

        date = datetime.today()
        today_str = self.get_date_string(
            date, ('plan' if is_planned else 'avar'))

        if recieved_data:
            past = 0
            for item in recieved_data:
                print(item)
                if len(item) == 1:
                    if today_str in item[0]:  # find work today
                        past = 1
                        result_text = "<b>" + \
                            ("Аварійні" if not is_planned else "Планові") + \
                            f" роботи {today_str}</b>\n\n"
                    else:
                        past = 0

                if len(item) == 5 and past == 1 and len([x for x in config.OBSERVABLE_PLACES if x in item[1]]) != 0:
                    (_, streets, reason, times, _) = item

                    for el in re.findall(config.STREET_REGEX, streets):
                        pl, inf = map(str, el)
                        pl = pl.replace("\n", "")
                        if pl in config.OBSERVABLE_PLACES:
                            streets_number = inf.replace("\n", "").split('; ')
                            temp = "\n".join(
                                [f"🔸{st}" for st in streets_number])
                            data = dict(place=pl, streets=temp,
                                        reason=reason, times=times)
                            result_text += self.render(data)
            result_text = result_text
        return result_text

    def broadcast(self, chat_id: int, message: str) -> None:
        if len(message) <= 4000:
            self.bot.send_message(chat_id, message, parse_mode='HTML')
        else:
            messages = message.split('\n\n')
            [self.bot.send_message(chat_id, msg, parse_mode='HTML')
             for msg in messages if msg != '']

    def shedule(self, chat_id: int, is_silent_pin: bool) -> None:
        data = self.get_accident_work(config.URL_PLANNED)
        mess_plan = self.format_tech_works(data)
        m = self.bot.send_message(chat_id, mess_plan, parse_mode='HTML')
        self.bot.pin_chat_message(chat_id, m.message_id, is_silent_pin)

        data = self.get_accident_work(config.URL_ACCIDENT)
        mess_avar = self.format_tech_works(data, False)
        self.bot.send_message(chat_id, mess_avar, parse_mode='HTML')

    def schedule_start(self) -> None:
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

        data = cls.get_accident_work(cls, url=config.URL_PLANNED)
        mess_plan = cls.format_tech_works(cls, data, True)

        cls.broadcast(cls, message.chat.id, mess_plan)

    @classmethod
    def accident_handler(cls, message):
        if message.from_user.id != message.chat.id:
            cls.bot.delete_message(message.chat.id, message.message_id)

        data = cls.get_accident_work(cls, url=config.URL_ACCIDENT)
        mess_avar = cls.format_tech_works(cls, data, False)

        cls.broadcast(cls, message.chat.id, mess_avar)

    @classmethod
    def help_handler(cls, message):
        mess = ("/planned - Перевірити планові роботи\n"
                "/avaria - Перевірити аварійні відключення\n\n"
                "Інформація представлена сайтом https://ksoe.com.ua/\n"
                "⚠️ Дані відображаються поки що тільки для таких населенних пунктів:\n" +
                ", ".join([f"<b>{i}</b>" for i in config.OBSERVABLE_PLACES]) +
                f"\n\n🤖За пропозиціями і побажаннями щодо покращення роботи бота - звертатися до <a href='tg://user?id={config.admin}'>мого розробника</a>")
        cls.bot.send_message(message.chat.id, mess, parse_mode='HTML',
                             disable_web_page_preview=True)

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
    # bot = TeleBot(config.BOT_TOKEN)
    ksoebot = KsoeBot()
    ksoebot.run()
