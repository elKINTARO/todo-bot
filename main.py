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

from database import init_db, add_task, get_tasks, mark_task_done, delete_task_db

load_dotenv()
TOKEN = os.getenv("TG_TOKEN")
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

GET_TASK_TEXT, GET_DEADLINE = range(2)

#Logic bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        f"Здоров, {user.first_name}! \n\n"
        f"Я твій особистий TODO-бот. "
        f"Надішли мені команду, і я допоможу тобі організувати завдання. "
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
        reply_markup=ReplyKeyboardRemove()
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
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Дію скасовано.", reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    tasks = get_tasks(user.id)

    if not tasks:
        await update.message.reply_text("🎉 Чудова робота! У вас немає активних завдань.")
        return

    response_lines = ["<b>📋 Ваші активні завдання:</b>", ""]
    for task in tasks:
        response_lines.append(f"• {task['task_text']} (ID: <code>{task['id']}</code>)")

    response_lines.append("\nЩоб позначити завдання як виконане, використовуйте:\n"
                          "<code>/done [ID завдання]</code>")

    response_text = "\n".join(response_lines)
    await update.message.reply_html(response_text)

async def done_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not context.args:
        await update.message.reply_text(
            "Будь ласка, вкажіть ID завдання.\n"
            "Наприклад: <code>/done 123</code>",
            parse_mode="HTML"
        )
        return
    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID завдання має бути числом.")
        return

    rows_affected =mark_task_done(user.id, task_id)

    if rows_affected:
        await update.message.reply_text(f"✅ Завдання (ID: {task_id}) позначено як виконане!")
    else:
        await update.message.reply_text(
            f"❌ Завдання з ID {task_id} не знайдено серед ваших активних завдань."
        )


async def delete_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    if not context.args:
        await update.message.reply_text(
            "Будь ласка, вкажіть ID завдання для видалення.\n"
            "Наприклад: <code>/delete 123</code>",
            parse_mode="HTML"
        )
        return

    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID завдання має бути числом.")
        return

    rows_affected = delete_task_db(user.id, task_id)

    if rows_affected > 0:
        await update.message.reply_text(f"🗑️ Завдання (ID: {task_id}) успішно видалено.")
    else:
        await update.message.reply_text(
            f"❌ Завдання з ID {task_id} не знайдено."
        )

def main() -> None:
    #init db
    init_db()
    logger.info("Базу даних ініціалізовано")
    #create app
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("new", new_task_start)],
        states={
            #wait text
            GET_TASK_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_task_text)
            ],
            #wait deadline
            GET_DEADLINE: [
                MessageHandler(filters.Regex("^Пропустити$"), skip_deadline),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_deadline)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler) #dialog create task
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("list", list_tasks)) #show your tasks
    application.add_handler(CommandHandler("done", done_task)) #done task
    application.add_handler(CommandHandler("delete", delete_task)) #delete task
    print("Бот запускається... Натисніть Ctrl+C для зупинки.")
    application.run_polling()

if __name__ == "__main__":
    main()


