import logging
import sqlite3
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

TOKEN = "8636706231:AAHSJ7ywK_qcMIHaB0QhlNLWZ_mjAI__xaE"

logging.basicConfig(level=logging.INFO)

conn = sqlite3.connect("bot.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS masters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT,
    phone TEXT,
    category TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER,
    district TEXT,
    category TEXT,
    description TEXT,
    phone TEXT,
    status TEXT
)
""")

conn.commit()

districts = {
    "ru": ["Внутри города","Кучкак","Шуркургон","Равот","Патар","Вогзал","Каранток"],
    "tj": ["Дохили шаҳр","Кӯчкак","Шӯрқӯрғон","Равот","Патар","Вогзал","Қарантоқ"]
}

categories = {
    "ru": ["Сантехника","Электрика","Мебель","Двери","Окна"],
    "tj": ["Сантехника","Барқ","Мебел","Дарҳо","Тирезаҳо"]
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["🇷🇺 Русский"], ["🇹🇯 Тоҷикӣ"]]
    await update.message.reply_text("Выберите язык / Забонро интихоб кунед:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def choose_language(update, context):
    context.user_data["lang"] = "ru" if "Русский" in update.message.text else "tj"

    keyboard = [["Создать заказ","Я мастер"]] if context.user_data["lang"]=="ru" else [["Эҷоди фармоиш","Ман усто"]]

    await update.message.reply_text(
        "Выберите действие:" if context.user_data["lang"]=="ru" else "Амалро интихоб кунед:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def choose_district(update, context):
    lang = context.user_data["lang"]
    keyboard = [[d] for d in districts[lang]]
    await update.message.reply_text(
        "Выберите район:" if lang=="ru" else "Ноҳияро интихоб кунед:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def choose_category(update, context):
    lang = context.user_data["lang"]
    keyboard = [[c] for c in categories[lang]]
    await update.message.reply_text(
        "Выберите категорию:" if lang=="ru" else "Категорияро интихоб кунед:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def register_master(update, context):
    lang = context.user_data["lang"]
    await update.message.reply_text("Введите имя:" if lang=="ru" else "Номро нависед:")
    context.user_data["step"] = "master_name"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    lang = context.user_data.get("lang")

    if text in ["🇷🇺 Русский","🇹🇯 Тоҷикӣ"]:
        await choose_language(update, context)
        return

    if text in ["Создать заказ","Эҷоди фармоиш"]:
        await choose_district(update, context)
        return

    if text in ["Я мастер","Ман усто"]:
        await register_master(update, context)
        return

    if lang and text in districts[lang]:
        context.user_data["district"] = text
        await choose_category(update, context)
        return

    if lang and text in categories[lang]:
        context.user_data["category"] = text

        if context.user_data.get("step") == "master_category":
            cursor.execute("INSERT INTO masters (user_id,name,phone,category) VALUES (?,?,?,?)",
                (update.message.from_user.id,
                 context.user_data["name"],
                 context.user_data["phone"],
                 text))
            conn.commit()

            await update.message.reply_text("✅ Вы мастер!" if lang=="ru" else "✅ Шумо усто шудед!")
            context.user_data.clear()
            return

        await update.message.reply_text("Опишите заказ:" if lang=="ru" else "Тавсиф нависед:")
        context.user_data["step"] = "desc"
        return

    if context.user_data.get("step") == "desc":
        context.user_data["desc"] = text
        await update.message.reply_text("Введите телефон:" if lang=="ru" else "Телефон:")
        context.user_data["step"] = "phone"
        return

    if context.user_data.get("step") == "phone":
        context.user_data["phone"] = text

        cursor.execute("""INSERT INTO orders 
        (client_id,district,category,description,phone,status)
        VALUES (?,?,?,?,?,?)""",
            (update.message.from_user.id,
             context.user_data["district"],
             context.user_data["category"],
             context.user_data["desc"],
             text,
             "new"))
        order_id = cursor.lastrowid
        conn.commit()

        cursor.execute("SELECT user_id FROM masters WHERE category=?", (context.user_data["category"],))
        masters = cursor.fetchall()

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔥 Взять заказ", callback_data=f"take_{order_id}")]
        ])

        for m in masters:
            try:
                await context.bot.send_message(
                    chat_id=m[0],
                    text=f"🔥 Новый заказ!\n\n{context.user_data['category']}\n{context.user_data['desc']}\n📞 {text}",
                    reply_markup=keyboard
                )
            except:
                pass

        await update.message.reply_text("✅ Заказ создан!")
        context.user_data.clear()
        return

    if context.user_data.get("step") == "master_name":
        context.user_data["name"] = text
        await update.message.reply_text("Телефон:")
        context.user_data["step"] = "master_phone"
        return

    if context.user_data.get("step") == "master_phone":
        context.user_data["phone"] = text
        await choose_category(update, context)
        context.user_data["step"] = "master_category"
        return

# 🔥 КНОПКА
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    order_id = int(query.data.split("_")[1])

    # получаем заказ
    cursor.execute("SELECT client_id FROM orders WHERE id=?", (order_id,))
    order = cursor.fetchone()

    # получаем мастера
    cursor.execute("SELECT name, phone FROM masters WHERE user_id=?", (query.from_user.id,))
    master = cursor.fetchone()

    # обновляем статус
    cursor.execute("UPDATE orders SET status='taken' WHERE id=?", (order_id,))
    conn.commit()

    # сообщение мастеру
    await query.edit_message_text("✅ Вы взяли заказ!")

    # отправка клиенту
    if order and master:
        client_id = order[0]
        name, phone = master

        await context.bot.send_message(
            chat_id=client_id,
            text=f"👷 Ваш мастер найден!\n\nИмя: {name}\nТелефон: {phone}"
        )

# ▶️ запуск
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button))

    print("БОТ ФИНАЛЬНЫЙ ЗАПУЩЕН 🚀")
    app.run_polling()

if __name__ == "__main__":
    main()
