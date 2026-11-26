import os
import sqlite3
from contextlib import closing
from pathlib import Path
from xml.etree.ElementTree import ParseError

import httpx
from telegram import ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from patents import EXAMPLE, lookup

DB = Path(__file__).with_name("settings.sqlite3")
KEYBOARD = ReplyKeyboardMarkup([["Пример", "Формат"]], resize_keyboard=True)
HELP = ("Отправьте номер европейской публикации, например EP 1004359 B1, "
        "или команду /patent EP1004359B1.\n"
        "«Пример» запрашивает образец. «Формат» или /format переключает вид карточки.")


def preference(user_id, toggle=False):
    with closing(sqlite3.connect(DB)) as db, db:
        db.execute("CREATE TABLE IF NOT EXISTS settings (user_id INTEGER PRIMARY KEY, detailed INTEGER NOT NULL)")
        if toggle:
            db.execute("INSERT INTO settings VALUES (?, 0) ON CONFLICT(user_id) "
                       "DO UPDATE SET detailed = 1 - detailed", (user_id,))
        row = db.execute("SELECT detailed FROM settings WHERE user_id = ?", (user_id,)).fetchone()
    return bool(row[0]) if row else True


async def help_message(update, context):
    await update.effective_message.reply_text(HELP, reply_markup=KEYBOARD)


async def handle(update, context):
    message = update.effective_message
    text = message.text.strip()
    command = text.split()[0].split("@")[0].lower()
    try:
        user_id = update.effective_user.id
        if text == "Формат" or command == "/format":
            detailed = preference(user_id, toggle=True)
            answer = "Теперь карточка подробная." if detailed else "Теперь карточка краткая."
        else:
            if command == "/patent":
                text = " ".join(context.args)
            elif text == "Пример":
                text = EXAMPLE
            answer = await lookup(text, preference(user_id))
    except ValueError as error:
        answer = str(error)
    except httpx.TimeoutException:
        answer = "EPO не успело ответить. Повторите запрос через минуту."
    except (httpx.HTTPError, ParseError):
        answer = "Не удалось прочитать документ EPO. Попробуйте позже."
    except sqlite3.Error:
        answer = "Не удалось открыть настройки. Проверьте доступ к файлу базы."
    await message.reply_text(answer, reply_markup=KEYBOARD)


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Задайте переменную TELEGRAM_BOT_TOKEN перед запуском.")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler(["start", "help"], help_message))
    app.add_handler(CommandHandler(["patent", "format"], handle))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.run_polling()


if __name__ == "__main__":
    main()

