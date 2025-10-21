import telebot
import pandas as pd
from io import BytesIO
import re

TOKEN = "8204801402:AAEiLD24Eg-6XSSmgId6N93U4oM1NJ3RxPc"
ADMIN_ID = 712270836  # Твой ID
bot = telebot.TeleBot(TOKEN)

# === Загружаем справочник товаров ===
excel_path = "Мерч_позиции_средняя цена (1) (1).xlsx"
df_products = pd.read_excel(excel_path)

# Функция, чтобы брать верхнюю границу, если диапазон
def parse_price(val):
    if isinstance(val, str):
        # находим все числа в ячейке
        nums = re.findall(r"\d+", val.replace(" ", ""))
        if len(nums) == 2:
            return int(nums[1])  # берём большую
        elif len(nums) == 1:
            return int(nums[0])
        else:
            return 0
    elif isinstance(val, (int, float)):
        return int(val)
    return 0

product_names = df_products.iloc[:, 0].tolist()
product_prices = [parse_price(x) for x in df_products.iloc[:, 1].tolist()]

# === Временные данные пользователей ===
user_data = {}

countries = ["Беларусь", "Казахстан", "Армения", "Узбекистан", "Кыргызстан", "Китай", "Турция"]

# === START ===
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for c in countries:
        markup.add(c)
    bot.send_message(message.chat.id, "🌍 Выберите страну:", reply_markup=markup)
    bot.register_next_step_handler(message, select_country)

def select_country(message):
    country = message.text
    if country not in countries:
        bot.send_message(message.chat.id, "❗️Выберите страну из списка.")
        return start(message)
    user_data[message.chat.id] = {"country": country, "items": {}}
    send_next_product(message.chat.id, 0)

def send_next_product(chat_id, index):
    if index >= len(product_names):
        bot.send_message(chat_id, "✅ Все позиции пройдены. Напишите *Готово*, чтобы отправить данные.", parse_mode='Markdown')
        bot.register_next_step_handler_by_chat_id(chat_id, finish_submission)
        return

    name = product_names[index]
    price = product_prices[index]
    bot.send_message(chat_id, f"🛍 {name}\n💰 Средняя цена: {price}\n\nВведите количество (или 0, если не нужно):")
    bot.register_next_step_handler_by_chat_id(chat_id, lambda msg: save_quantity(msg, index))

def save_quantity(message, index):
    chat_id = message.chat.id
    try:
        qty = int(message.text)
    except ValueError:
        bot.send_message(chat_id, "Введите число.")
        return send_next_product(chat_id, index)

    name = product_names[index]
    price = product_prices[index]
    user_data[chat_id]["items"][name] = {"qty": qty, "price": price}
    send_next_product(chat_id, index + 1)

def finish_submission(message):
    chat_id = message.chat.id
    data = user_data.get(chat_id)
    if not data:
        return bot.send_message(chat_id, "Данные не найдены. Начните заново /start")

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

    if not results:
        bot.send_message(chat_id, "Вы не выбрали ни одной позиции.")
        return

    df = pd.DataFrame(results)
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    bot.send_message(chat_id, "✅ Данные отправлены руководителю, спасибо!")
    bot.send_document(ADMIN_ID, output, visible_file_name=f"Мерч_{country}.xlsx")

# === Запуск ===
bot.polling(none_stop=True)
