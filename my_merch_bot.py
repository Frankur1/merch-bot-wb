import telebot
import pandas as pd
from io import BytesIO
import re

TOKEN = "8204801402:AAEiLD24Eg-6XSSmgId6N93U4oM1NJ3RxPc"
ADMIN_ID = 712270836
bot = telebot.TeleBot(TOKEN)

excel_path = "merch_positions.xlsx"
df_products = pd.read_excel(excel_path)

def parse_price(val):
    if isinstance(val, str):
        nums = re.findall(r"\d+", val.replace(" ", ""))
        if len(nums) == 2:
            return int(nums[1])
        elif len(nums) == 1:
            return int(nums[0])
        else:
            return 0
    elif isinstance(val, (int, float)):
        return int(val)
    return 0

product_names = df_products.iloc[:, 0].tolist()
product_prices = [parse_price(x) for x in df_products.iloc[:, 1].tolist()]
user_data = {}

countries = ["Беларусь", "Казахстан", "Армения", "Узбекистан", "Кыргызстан", "Китай", "Турция"]

@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for c in countries:
        markup.add(c)
    bot.send_message(message.chat.id,
        "👋 Привет!\n\nЭтот бот помогает собрать потребности в мерче на год 🎁\n\n"
        "🌍 Выберите вашу страну:", reply_markup=markup)
    bot.register_next_step_handler(message, select_country)

def select_country(message):
    country = message.text
    if country not in countries:
        bot.send_message(message.chat.id, "❗️Пожалуйста, выберите страну из списка.")
        return start(message)

    user_data[message.chat.id] = {"country": country, "items": {}}
    show_full_list(message.chat.id)

def show_full_list(chat_id):
    text = "📦 Полный список доступных товаров:\n\n"
    for i, (name, price) in enumerate(zip(product_names, product_prices), 1):
        text += f"{i}. {name} — {price} ֏\n"
    text += "\nТеперь пройдёмся по каждому товару 👇"
    bot.send_message(chat_id, text)
    send_next_product(chat_id, 0)

def send_next_product(chat_id, index):
    if index >= len(product_names):
        return confirm_selection(chat_id)

    name = product_names[index]
    price = product_prices[index]
    progress = f"({index+1}/{len(product_names)})"
    bot.send_message(chat_id,
        f"🛍 {progress}\n{name}\n💰 Средняя цена: {price} ֏\n\nВведите количество (0 — если не нужно):")
    bot.register_next_step_handler_by_chat_id(chat_id, lambda msg: save_quantity(msg, index))

def save_quantity(message, index):
    chat_id = message.chat.id
    try:
        qty = int(message.text)
    except ValueError:
        bot.send_message(chat_id, "Введите число, пожалуйста 🙂")
        return send_next_product(chat_id, index)

    name = product_names[index]
    price = product_prices[index]
    user_data[chat_id]["items"][name] = {"qty": qty, "price": price}
    send_next_product(chat_id, index + 1)

def confirm_selection(chat_id):
    data = user_data.get(chat_id)
    items = data["items"]
    country = data["country"]

    summary = f"📋 Проверим данные по стране: *{country}*\n\n"
    total = 0
    for name, info in items.items():
        qty = info["qty"]
        price = info["price"]
        if qty > 0:
            subtotal = qty * price
            total += subtotal
            summary += f"• {name}: {qty} шт × {price} ֏ = {subtotal} ֏\n"
    summary += f"\n💰 *Итого:* {total} ֏\n\nОтправляем данные?"
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("✅ Да, отправить", callback_data="confirm_send"),
        telebot.types.InlineKeyboardButton("✏️ Исправить", callback_data="restart")
    )
    bot.send_message(chat_id, summary, parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["confirm_send", "restart"])
def handle_confirm(call):
    chat_id = call.message.chat.id
    if call.data == "restart":
        return start(call.message)

    data = user_data.get(chat_id)
    items = data["items"]
    country = data["country"]

    results = []
    for name, info in items.items():
        qty = info["qty"]
        price = info["price"]
        if qty > 0:
            results.append({
                "Страна": country,
                "Позиция": name,
                "Кол-во": qty,
                "Средняя цена": price,
                "Сумма": qty * price
            })

    df = pd.DataFrame(results)
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    bot.send_message(chat_id, "✅ Спасибо! Данные отправлены руководителю.")
    bot.send_document(ADMIN_ID, output, visible_file_name=f"Мерч_{country}.xlsx")

bot.polling(none_stop=True)
