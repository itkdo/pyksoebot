import telebot
from telebot import apihelper
from datetime import datetime
import time
import traceback
from threading import Thread
import cherrypy
import requests
import schedule
import re

from bs4 import BeautifulSoup


TOKEN = ""
url_plan_work = 'https://ksoe.com.ua/disconnection/planned/'
url_accident_work = 'https://ksoe.com.ua/disconnection/outages/'

admin = 0
rubinchat = 0

places_list = ["Нова Каховка","Веселе", "Козацьке", "Одрадокам'янка", "Дніпряни", "Бургунка", "Миколаївка"]

place = ['gpres', 'nkres','vpres','hges','kvres','ntres','gnres','ivres','vlres','cpres','skres', 'crres']
regexp = r"([\w\s'’/-]+):\s\n\n?(.+)"


bot = telebot.TeleBot(TOKEN)


class WebhookServer(object):
	@cherrypy.expose
	def index(self):
		length = int(cherrypy.request.headers['content-length'])
		json_string = cherrypy.request.body.read(length).decode("utf-8")
		update = telebot.types.Update.de_json(json_string)
		bot.process_new_updates([update])
		return ''


def report(place, streets, reason, times):
	return(f"<b>{place}:</b>\n"
			f"<code>{streets}</code>\n"
			f"⚡️: <code>{reason}</code>\n"
			f"⏱: <code>{times}</code>\n\n")


def now(date, act):
	if act == 'plan':
		return f"{int(date.day)}.{int(date.month)}.{date.year}"
	elif act == 'avar':
		return date.strftime('%d.%m.%Y')


def cleanhtml(raw_html):
	cleanr = re.compile('<.*?>')
	cleantext = re.sub(cleanr, '', str(raw_html))
	return cleantext


def get_accident_work(url, res_id = "nkres"):
	data = []
	try:
		response = requests.get(url, data={'tname': res_id}, headers= {'User-agent': 'Mozilla/5.0'})
		html = response.content
		soup = BeautifulSoup(html, 'lxml')
				
		table = soup.find('table', attrs={'class':'table-otkl'})
		table_body = table.find('tbody')

		rows = table_body.find_all('tr')
		for row in rows:
			cols = row.find_all('td')
			cols = [cleanhtml(str(ele).replace('<br/>', '\n').replace('<br><br>',"\n")) for ele in cols]
			data.append([ele for ele in cols if ele])
	except:
		bot.send_message(admin, str(traceback.format_exc()))
		print(traceback.format_exc())
		return data
	return data


def format_tech_works(recieved_data, is_planned = True):
	if is_planned:  result_text = "Сьогодні немає <b>планових</b> відключень."
	else: result_text = 'Сьогодні немає <b>запланованих</b> відключень.'

	today_str = now(datetime.today(), ('avar' if not is_planned else 'plan'))
	if recieved_data:
		past = 0
		check = 0
		outs = 0
		for item in recieved_data:
			if len(item) == 1:
				if today_str in item[0]: # find work today
					past = 1
					result_text = "<b>"+("Аварійні" if not is_planned else "Планові")+ f" роботи {today_str}</b>\n\n"
				else: past = 0
			if len(item) == 5 and past == 1 and len([x for x in places_list if x in item[1]]) != 0:
				(_, streets, reason, times, _) = item
				# if 'по' in times:
				# 	outs += 1
				# 	continue

				a = re.findall(regexp, streets)
				for el in a:
					pl, inf = map(str, el)
					pl = pl.replace("\n", "")
					if pl in places_list:
						streets_number = inf.replace("\n", "").split('; ')
						temp = "\n".join([f"🔸{st}" for st in streets_number])
						result_text += report(pl, temp, reason, times)
				check = 1
		result_text = result_text #+ (f"Сьогодні було <b>{outs}</b> " + ("відключення" if outs < 5 else "відключень")) if outs > 0 else ""
		# if check == 0:
		# 	result_text = "Сьогодні немає <b>аварійних</b> відключень."
	return result_text


def shedule(chat_id, silent_pin):
	data = get_accident_work(url_plan_work)
	mess_plan = format_tech_works(data)
	m = bot.send_message(chat_id, mess_plan, parse_mode = 'HTML')
	bot.pin_chat_message(chat_id, m.message_id, silent_pin)
		
	data = get_accident_work(url_accident_work)
	mess_avar = format_tech_works(data, False)
	bot.send_message(chat_id, mess_avar, parse_mode = 'HTML')


def schedule_start():
	schedule.every().day.at('08:15').do(shedule, rubinchat, True)
	schedule.every().day.at('13:15').do(shedule, rubinchat, True)
	# schedule.every().day.at('19:17').do(shedule, -466248839, True)
	while True:
		schedule.run_pending()
		time.sleep(1)		
		



# @bot.message_handler(commands=["fill"])
# def fill(message):
# 	try:
# 		fill = get_json("fill.json")
# 		for i in place:
# 			print(f"getting data from {i}")
# 			all_places = []
# 			data = get_accident_work2(url_plan_work, i)
# 			if data:
# 				for list in data:
# 					if len(list) == 4:
# 						a = re.findall("([\w\s().'`’-]+):\s\n?\n?(.+)", list[1])
# 						for el in a:
# 							pl, _ = map(str, el)
# 							pl = pl.replace("\n", "").strip()
# 							if pl not in all_places and pl not in ['В т.ч. особ. рахунки пром.', 'Особ. рахунки пром.']:
# 								all_places.append(pl)
# 			data = get_accident_work2(url_accident_work, i)
# 			if data:
# 				for list in data:
# 					if len(list) == 5:
# 						a = re.findall("([\w\s().'`’-]+):\s\n?\n?(.+)", list[1])
# 						for el in a:
# 							pl, _ = map(str, el)
# 							pl = pl.replace("\n", "").strip()
# 							if pl not in all_places and pl not in ['В т.ч. особ. рахунки пром.', 'Особ. рахунки пром.']:
# 								all_places.append(pl)
# 			fill[i] = sorted(all_places)
# 			time.sleep(5)
# 		save_json("fill.json", fill)
# 		print("job done")
# 	except:
# 		print(traceback.format_exc())
	
@bot.message_handler(commands=["start"])
def start(message):
	bot.send_message(message.chat.id, "Привіт! Я бот для перевірки стану ремонтних робіт електромереж у Херсонській області.\nТисни /help, щоб дізнатися що я вмію.")
		
@bot.message_handler(commands=["id"])
def id(message):
	try:	
		if message.reply_to_message:
			bot.send_message(message.chat.id, f"{message.reply_to_message.from_user.id}")
		else:
			bot.send_message(message.chat.id, f"{message.chat.id}")
			
		if message.from_user.id != message.chat.id:
			bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
	except apihelper.ApiException:
		pass


@bot.message_handler(commands=["planned"])
def planned(message):
	if message.from_user.id != message.chat.id:
		bot.delete_message(message.chat.id, message.message_id)

	data = get_accident_work(url_plan_work)
	mess_plan = format_tech_works(data, True)
	
	if len(mess_plan) <= 4000:
		bot.send_message(message.chat.id, mess_plan, parse_mode = 'HTML')
	else:
		m = mess_plan.split('\n\n')
		[bot.send_message(message.chat.id, m, parse_mode = 'HTML') for m in m if m != '']
			

@bot.message_handler(commands=["avaria"])
def accident(message):
	if message.from_user.id != message.chat.id:
		bot.delete_message(message.chat.id, message.message_id)

	data = get_accident_work(url_accident_work)
	mess_avar= format_tech_works(data, False)
	
	if len(mess_avar) <= 4000:
		bot.send_message(message.chat.id, mess_avar, parse_mode = 'HTML')
	else:
		m = mess_avar.split('\n\n')
		[bot.send_message(message.chat.id, m, parse_mode = 'HTML') for m in m if m != '']
			

@bot.message_handler(commands=["help"])
def help(message):
	mess = ("/planned - Перевірити планові роботи\n"
			"/avaria - Перевірити аварійні відключення\n\n"
			"Інформація представлена сайтом https://ksoe.com.ua/\n"
			"⚠️ Дані відображаються поки що тільки для таких населенних пунктів:\n" + 
			", ".join([f"<b>{i}</b>" for i in places_list]) +
			f"\n\n🤖За пропозиціями і побажаннями щодо покращення роботи бота - звертатися до <a href='tg://user?id={admin}'>мого розробника</a>")
	bot.send_message(message.chat.id, mess, parse_mode = 'HTML', disable_web_page_preview = True)


def init():
	try:
		print(f"{datetime.now().strftime('%d.%m.%Y %H:%M:%S')} - Bot start working")
		bot.delete_webhook()
		bot.set_webhook(url='https://darkest.online/avaria/')

		cherrypy.config.update({
		'server.socket_host': '127.0.0.1',
		'server.socket_port': 5001,
		'engine.autoreload.on': True})

		cherrypy.quickstart(WebhookServer(), '/', {'/': {}})
	except:
		print(f"{datetime.now().strftime('%d.%m.%Y %H:%M:%S')} - Fail set webhook. Starting with pollig")
		bot.delete_webhook()
		bot.polling(none_stop=True, interval=1, timeout=400000)


if __name__ == '__main__':
	Thread(target=schedule_start, daemon=True).start()
	init()	
