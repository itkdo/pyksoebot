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
import os

from bs4 import BeautifulSoup
import redis
import pickle
import sqlite3
import json

TOKEN = ""
bot = telebot.TeleBot(TOKEN)

headers = {'User-agent': 'Mozilla/5.0'}
rdata = {'tname':'nkres'}
WEBHOOK_URL = ""

url_plan_work = 'https://ksoe.com.ua/disconnection/planned/'
url_accident_work = 'https://ksoe.com.ua/disconnection/outages/'

#Telegram ids
admin = 0
rubinchat = 0

places_list = ['Нова Каховка','Веселе', 'Козацьке']
all_places = []

place = ['gpres', 'nkres','vpres','hges','kvres','ntres','gnres','ivres','vlres','cpres','skres', 'crres']

class WebhookServer(object):
	@cherrypy.expose
	def index(self):
		length = int(cherrypy.request.headers['content-length'])
		json_string = cherrypy.request.body.read(length).decode("utf-8")
		update = telebot.types.Update.de_json(json_string)
		bot.process_new_updates([update])
		return ''

def get_json(path):
	if not os.path.exists(path):
		with open(path, "w") as f:
			f.write("{}")
	with open(path, "r", encoding="utf-8") as f:
		return json.load(f)

def save_json(path, config):
	with open(path, "w", encoding="utf-8") as f:
		json.dump(config, f, indent=4, sort_keys=True, ensure_ascii=False)
	return True

def cleanhtml(raw_html):
	cleanr = re.compile('<.*?>')
	cleantext = re.sub(cleanr, '', raw_html)
	return cleantext

def get_accident_work(url):
	data = []
	try:
		response = requests.post(url, data=rdata, headers=headers)
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


def get_accident_work2(url, place):
	data = []
	try:
		d = {'tname': place}
		response = requests.post(url, data=d, headers=headers)
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

def shedule(chat_id, silent_pin):
	data = get_accident_work(url_plan_work)
	mess_plan = 'Сьогодні в Новій Каховці, Веселому та Козацькому немає ніяких <b>планових</b> робіт.'
	if data:
		dt = datetime.today()
		today = f'{int(dt.day)}.{int(dt.month)}.{dt.year}'
		past = 0
		check = 0
		for list in data:
			print(list)
			if len(list) == 1:
				if list[0] == today:
					past = 1
					mess_plan = f"<b>Заплановані роботи {today}</b>\n\n"
				else: past = 0
			if len(list) == 4 and past == 1 and len([x for x in places_list if x in list[1]]) != 0:
				a = re.findall("([\w\s'’-]+):\s\n?\n?(.+)", list[1])
				for el in a:
					pl, inf = map(str, el)
					pl = pl.replace("\n", "")
					if pl in places_list:
						streets_number = inf.replace("\n", "").split('; ')
						tmp = ""
						for x in streets_number: 
							tmp+=f"🔸{x}\n"
						mess_plan += f"<b>{pl}:</b>\n"\
						f"<code>{tmp}</code>\n"\
						f"⚡️: <code>{list[2]}</code>\n"\
						f"⏱: <code>{list[3]}</code>\n\n"
				check = 1
		if check == 0:
			mess_plan = f"Сьогодні в Новій Каховці, Веселому та Козацькому немає <b>планових</b> відключень."
		
	mess_avar = "Сьогодні в Новій Каховці, Веселому та Козацькому немає <b>аварійних</b> відключень."
	data = get_accident_work(url_accident_work)
	if data:
		dt = datetime.today().strftime('%d.%m.%Y')
		mess_avar = ""
		past = 0
		check = 0
		for list in data:
			if len(list) == 1:
				if dt in list[0]:
					past = 1
					mess_avar += f"<b>Аварійні роботи:</b>\n\n"
				else:
					past = 0
			if len(list) == 5 and past == 1 and len([x for x in places_list if x in list[1]]) != 0:
				a = re.findall("([\w\s'’-]+):\s\n\n?(.+)", list[1])
				for el in a:
					pl, inf = map(str, el)
					pl = pl.replace("\n", "")
					streets_number = inf.replace("\n", "").split('; ')
					tmp = ""
					for x in streets_number: 
						tmp+=f"🔸{x}\n"
					mess_avar += f"<b>{pl}:</b>\n"\
					f"<code>{tmp}</code>\n"\
					f"⚡️: <code>{list[2]}</code>\n"\
					f"⏱: <code>{list[3]}</code>\n\n"
				check = 1
		if check == 0:
			mess_avar = f"Сьогодні в Новій Каховці, Веселому та Козацькому немає <b>аварійних</b> відключень."	
			
	sheduler_message = f"{mess_plan}-----------------------------\n{mess_avar}"
	bot.send_message(admin, str(all_places))
	if len(sheduler_message) <= 4000:
		m = bot.send_message(chat_id, sheduler_message, parse_mode = 'HTML')
		bot.pin_chat_message(chat_id, m.message_id, silent_pin)
		# bot.send_message(admin, sheduler_message,parse_mode = 'HTML')
	else:
		bot.send_message(chat_id, mess_plan, parse_mode = 'HTML')
		bot.send_message(chat_id, mess_avar, parse_mode = 'HTML')
	

def schedule_start():
	schedule.every().day.at('09:15').do(shedule,rubinchat, True)
	schedule.every().day.at('14:15').do(shedule,rubinchat, True)
	while True:
		schedule.run_pending()
		time.sleep(1)		
		

@bot.message_handler(commands=["start"])
def start(message):
	bot.send_message(message.chat.id, "Привіт!")

@bot.message_handler(commands=["fill"])
def start(message):
	try:
		fill = get_json("fill.json")
		for i in place:
			print(f"getting data from {i}")
			all_places = []
			data = get_accident_work2(url_plan_work, i)
			if data:
				for list in data:
					if len(list) == 4:
						a = re.findall("([\w\s().'`’-]+):\s\n?\n?(.+)", list[1])
						for el in a:
							pl, _ = map(str, el)
							pl = pl.replace("\n", "").strip()
							if pl not in all_places and pl not in ['В т.ч. особ. рахунки пром.', 'Особ. рахунки пром.']:
								all_places.append(pl)
			data = get_accident_work2(url_accident_work, i)
			if data:
				for list in data:
					if len(list) == 5:
						a = re.findall("([\w\s().'`’-]+):\s\n?\n?(.+)", list[1])
						for el in a:
							pl, _ = map(str, el)
							pl = pl.replace("\n", "").strip()
							if pl not in all_places and pl not in ['В т.ч. особ. рахунки пром.', 'Особ. рахунки пром.']:
								all_places.append(pl)
			fill[i] = sorted(all_places)
			time.sleep(5)
		save_json("fill.json", fill)
		print("job done")
	except:
		print(traceback.format_exc())
	
	
@bot.message_handler(commands=["id"])
def id(message):
	if message.from_user.id != message.chat.id:
		bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
	try:
		if message.reply_to_message:
			bot.send_message(message.chat.id, f"{message.reply_to_message.from_user.id}")
		else:
			bot.send_message(message.chat.id, f"{message.chat.id}")
	except Exception:
		print(str(traceback.format_exc()))


@bot.message_handler(commands=["planned"])
def planned(message):
	if message.from_user.id != message.chat.id:
		bot.delete_message(message.chat.id, message.message_id)
	data = get_accident_work(url_plan_work)
	mess = 'Сьогодні в Новій Каховці, Веселому та Козацькому немає ніяких <b>планових</b> робіт.'
	if data:
		dt = datetime.today()
		today = f'{int(dt.day)}.{int(dt.month)}.{dt.year}'
		past = 0
		check = 0
		for list in data:
			print(list)
			if len(list) == 1:
				if list[0] == today:
					past = 1
					mess = f"<b>Заплановані роботи {today}</b>\n\n"
				else: past = 0
			if len(list) == 4 and past == 1 and len([x for x in places_list if x in list[1]]) != 0:
				a = re.findall("([\w\s'’-]+):\s\n?\n?(.+)", list[1])
				for el in a:
					pl, inf = map(str, el)
					pl = pl.replace("\n", "")
					if pl in places_list:
						streets_number = inf.replace("\n", "").split('; ')
						tmp = ""
						for x in streets_number: 
							tmp+=f"🔸{x}\n"
						mess += f"<b>{pl}:</b>\n"\
						f"<code>{tmp}</code>\n"\
						f"⚡️: <code>{list[2]}</code>\n"\
						f"⏱: <code>{list[3]}</code>\n\n"
				check = 1
			if len(list) == 4:
				a = re.findall("([\w\s'-]+):\s\n?\n?(.+)", list[1])
				for el in a:
					pl, inf = map(str, el)
					pl = pl.replace("\n", "")
					if pl not in all_places:
						all_places.append(pl)
		bot.send_message(admin, f"{sorted(all_places)}")
		if check == 0:
			mess = f"Сьогодні в Новій Каховці, Веселому та Козацькому немає <b>планових</b> відключень."
	if len(mess) <= 4000:
		bot.send_message(message.chat.id, mess, parse_mode = 'HTML')
	else:
		m = mess.split('\n\n')
		[bot.send_message(message.chat.id, m, parse_mode = 'HTML') for m in m if m != '']
	

@bot.message_handler(commands=["avaria"])
def accident(message):
	if message.from_user.id != message.chat.id:
		bot.delete_message(message.chat.id, message.message_id)
	data = get_accident_work(url_accident_work)
	if data:
		dt = datetime.today().strftime('%d.%m.%Y')
		mess = ""
		past = 0
		check = 0
		for list in data:
			if len(list) == 1:
				if dt in list[0]:
					past = 1
					mess += f"<b>Аварійні роботи {dt}:</b>\n\n"
				else:
					past = 0
			if len(list) == 5 and past == 1 and len([x for x in places_list if x in list[1]]) != 0:		
				a = re.findall("([\w\s'’-]+):\s\n\n?(.+)", list[1])
				for el in a:
					pl, inf = map(str, el)
					pl = pl.replace("\n", "")
					if pl in places_list:
						streets_number = inf.replace("\n", "").split('; ')
						tmp = ""
						for x in streets_number: 
							tmp+=f"🔸{x}\n"
						mess += f"<b>{pl}:</b>\n"\
						f"<code>{tmp}</code>\n"\
						f"⚡️: <code>{list[2]}</code>\n"\
						f"⏱: <code>{list[3]}</code>\n\n"
				check = 1
			if len(list) == 5:
				a = re.findall("([\w\s'-]+):\s\n?\n?(.+)", list[1])
				for el in a:
					pl, inf = map(str, el)
					pl = pl.replace("\n", "")
					if pl not in all_places:
						all_places.append(pl)
		bot.send_message(admin, f"{sorted(all_places)}")
		if mess == '' or check == 0:
			mess = f"Сьогодні в Новій Каховці, Веселому та Козацькому немає <b>аварійних</b> відключень."
	if len(mess) <= 4000:
		bot.send_message(message.chat.id, mess, parse_mode = 'HTML')
	else:
		m = mess.split('\n\n')
		[bot.send_message(message.chat.id, m, parse_mode = 'HTML') for m in m if m != '']
	

@bot.message_handler(commands=["help"])
def help(message):
	mess = "/planned - Перевірити планові роботи\n"\
			"/avaria - Перевірити аварійні відключення\n\n"\
			"Інформація представлена сайтом https://ksoe.com.ua/\n"\
			"⚠️ Дані відображаються тільки для таких населенних пунктів:\n"\
			"<b>Нова Каховка, Веселе, Козацьке</b>\n\n"\
			"🤖За пропозиціями і побажаннями щодо покращення роботи бота - звертатися до @herowins"
	bot.send_message(message.chat.id, mess, parse_mode = 'HTML', disable_web_page_preview = True)


def init():
	try:
		print(f"{datetime.now().strftime('%d.%m.%Y %H:%M:%S')} - Bot start working")
		bot.delete_webhook()
		bot.set_webhook(url=WEBHOOK_URL)
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
	