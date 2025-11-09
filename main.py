import logging
import os
from http.client import responses

from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    #for dialog
    ConversationHandler,
    MessageHandler,
    filters,
    )

from database import init_db, add_task, get_tasks, mark_task_done, delete_task_db, get_single_task, update_task_text

load_dotenv()
TOKEN = os.getenv("TG_TOKEN")
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

GET_TASK_TEXT, GET_DEADLINE = range(2)
EDIT_GET_ID, EDIT_GET_TEXT = range(2, 4)

MAIN_KEYBOARD_LAYOUT = [
    ["Нове завдання 📝"],
    ["Список завдань 📋", "Редагувати ✏️"],
    ["Завершити ✅", "Видалити 🗑️"],
]
MAIN_KEYBOARD_MARKUP = ReplyKeyboardMarkup(
    MAIN_KEYBOARD_LAYOUT,
    resize_keyboard=True,
)

#Logic bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        f"Здоров, {user.first_name}! \n\n"
        f"Я твій особистий TODO-бот. "
        f"Надішли мені команду, і я допоможу тобі організувати завдання. ",
        reply_markup=MAIN_KEYBOARD_MARKUP
    )

async def new_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Гаразд, нове завдання. \n"
        "Напиши мені його текст. (або /cancel для скасування)"
    )
    return GET_TASK_TEXT

async def receive_task_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    task_text = update.message.text
    context.user_data["current_task_text"] = task_text
    reply_keyboard = [["Пропустити"]]
    await update.message.reply_text(
        "✅ Текст збережено!\n"
        "Тепер введи дедлайн (наприклад, 'завтра о 15:00' або '25.12').\n\n"
        "Або просто натисни 'Пропустити'.",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
    )
    return GET_DEADLINE

async def receive_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    deadline = update.message.text
    user = update.effective_user
    task_text = context.user_data["current_task_text"]
    add_task(user.id, task_text, deadline)

    await update.message.reply_text(
        f"✅ Завдання додано:\n"
        f"<b>{task_text}</b>\n"
        f"<i>Дедлайн: {deadline}</i>",
        parse_mode="HTML",
        reply_markup=MAIN_KEYBOARD_MARKUP
    )
    context.user_data.clear()
    return ConversationHandler.END

async def skip_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    task_text = context.user_data["current_task_text"]
    add_task(user.id, task_text)

    await update.message.reply_text(
        f"✅ Завдання додано:\n"
        f"<b>{task_text}</b> (без дедлайну)",
        parse_mode="HTML",
        reply_markup=MAIN_KEYBOARD_MARKUP
    )
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Дію скасовано.", reply_markup=MAIN_KEYBOARD_MARKUP
    )
    return ConversationHandler.END


async def edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user

    tasks = get_tasks(user.id)
    if not tasks:
        await update.message.reply_text("У вас немає активних завдань для редагування.")
        return ConversationHandler.END

    response_lines = ["<b>Яке завдання ви хочете редагувати?</b>\n"]
    for task in tasks:
        response_lines.append(f"• <code>{task['id']}</code>: {task['task_text']}")

    response_lines.append("\nНапишіть ID завдання (або /cancel для скасування).")

    await update.message.reply_html("\n".join(response_lines))

    return EDIT_GET_ID

async def edit_receive_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user

    try:
        task_id = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Це не схоже на ID. Будь ласка, введіть число.")
        return EDIT_GET_ID

    task = get_single_task(user.id, task_id)

    if not task:
        await update.message.reply_text("❌ Завдання з таким ID не знайдено.")
        return EDIT_GET_ID

    context.user_data['edit_task_id'] = task_id

    await update.message.reply_html(
        f"Гаразд, редагуємо завдання:\n"
        f"<i>{task['task_text']}</i>\n\n"
        f"Тепер надішли мені <b>новий текст</b> для цього завдання."
    )
    return EDIT_GET_TEXT


async def edit_receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    new_text = update.message.text

    task_id = context.user_data['edit_task_id']

    success = update_task_text(user.id, task_id, new_text)

    if success:
        await update.message.reply_html(
            f"✅ Завдання (ID: {task_id}) оновлено:\n<b>{new_text}</b>",
            reply_markup=MAIN_KEYBOARD_MARKUP
        )
    else:
        await update.message.reply_text(
            "❌ Сталася несподівана помилка при оновленні.",
            reply_markup=MAIN_KEYBOARD_MARKUP
        )

    context.user_data.clear()

    return ConversationHandler.END

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    tasks = get_tasks(user.id)

    if not tasks:
        await update.message.reply_text(
            "🎉 Чудова робота! У вас немає активних завдань.",
            reply_markup=MAIN_KEYBOARD_MARKUP
            )
        return

    response_lines = ["<b>📋 Ваші активні завдання:</b>", ""]
    for task in tasks:
        response_lines.append(f"• {task['task_text']} (ID: <code>{task['id']}</code>)")

    response_lines.append("\nЩоб позначити завдання як виконане, використовуйте:\n"
                          "<code>/done [ID завдання]</code>")

    response_text = "\n".join(response_lines)
    await update.message.reply_html(
        response_text,
        reply_markup=MAIN_KEYBOARD_MARKUP
    )

async def done_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not context.args:
        await update.message.reply_text(
            "Будь ласка, вкажіть ID завдання.\n"
            "Наприклад: <code>/done 123</code>",
            parse_mode="HTML",
            reply_markup=MAIN_KEYBOARD_MARKUP
        )
        return
    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "ID завдання має бути числом.",
            reply_markup=MAIN_KEYBOARD_MARKUP
        )
        return

    rows_affected =mark_task_done(user.id, task_id)

    if rows_affected:
        await update.message.reply_text(
            f"✅ Завдання (ID: {task_id}) позначено як виконане!",
            reply_markup=MAIN_KEYBOARD_MARKUP
        )
    else:
        await update.message.reply_text(
            f"❌ Завдання з ID {task_id} не знайдено серед ваших активних завдань.",
            reply_markup=MAIN_KEYBOARD_MARKUP
        )


async def delete_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    if not context.args:
        await update.message.reply_text(
            "Будь ласка, вкажіть ID завдання для видалення.\n"
            "Наприклад: <code>/delete 123</code>",
            parse_mode="HTML",
            reply_markup=MAIN_KEYBOARD_MARKUP
        )
        return

    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "ID завдання має бути числом.",
            reply_markup=MAIN_KEYBOARD_MARKUP
        )
        return

    rows_affected = delete_task_db(user.id, task_id)

    if rows_affected > 0:
        await update.message.reply_text(
            f"🗑️ Завдання (ID: {task_id}) успішно видалено.",
            reply_markup=MAIN_KEYBOARD_MARKUP
        )
    else:
        await update.message.reply_text(
            f"❌ Завдання з ID {task_id} не знайдено.",
            reply_markup=MAIN_KEYBOARD_MARKUP
        )


def main() -> None:
    #init db
    init_db()
    logger.info("Базу даних ініціалізовано.")
    #build app
    application = Application.builder().token(TOKEN).build()

    new_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("new", new_task_start),
            MessageHandler(filters.Regex("^Нове завдання 📝$"), new_task_start)
        ],
        states={
            GET_TASK_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_task_text)],
            GET_DEADLINE: [
                MessageHandler(filters.Regex("^Пропустити$"), skip_deadline),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_deadline),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    edit_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("edit", edit_start),
            MessageHandler(filters.Regex("^Редагувати ✏️$"), edit_start)
        ],
        states={
            EDIT_GET_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_receive_id)],
            EDIT_GET_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_receive_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(new_conv_handler)
    application.add_handler(edit_conv_handler)
    #start
    application.add_handler(CommandHandler("start", start))
    #list
    application.add_handler(CommandHandler("list", list_tasks))
    application.add_handler(MessageHandler(filters.Regex("^Список завдань 📋$"), list_tasks))
    #done
    application.add_handler(CommandHandler("done", done_task))
    application.add_handler(MessageHandler(filters.Regex("^Завершити ✅$"), done_task))
    #delete
    application.add_handler(CommandHandler("delete", delete_task))
    application.add_handler(MessageHandler(filters.Regex("^Видалити 🗑️$"), delete_task))

    application.add_handler(CommandHandler("cancel", cancel))

    print("Бот запускається... Натисніть Ctrl+C для зупинки.")
    application.run_polling()


if __name__ == "__main__":
    main()


