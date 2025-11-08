import logging
import os
from http.client import responses

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackContext

from database import init_db, add_task, get_tasks, mark_task_done, delete_task_db

load_dotenv()
TOKEN = os.getenv("TG_TOKEN")
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

#Logic bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        f"Здоров, {user.first_name}! \n\n"
        f"Я твій особистий TODO-бот. "
        f"Надішли мені команду, і я допоможу тобі організувати завдання. "
    )

async def new_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    task_text = " ".join(context.args)

    if not task_text:
        await update.message.reply_text(
            "Введіть будь ласка текст завдання після команди \n"
            "Наприклад: '/new Написати звіт'",
            parse_mode="MarkdownV2"
        )
        return

    success = add_task(user.id, task_text)
    if success:
        await update.message.reply_text(f"✅ Завдання додано:\n\n{task_text}")
    else:
        await update.message.reply_text("❌ Сталася помилка. Не вдалося додати завдання.")

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

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new", new_task)) #create task
    application.add_handler(CommandHandler("list", list_tasks)) #show your tasks
    application.add_handler(CommandHandler("done", done_task)) #done task
    application.add_handler(CommandHandler("delete", delete_task)) #delete task
    print("Бот запускається... Натисніть Ctrl+C для зупинки.")
    application.run_polling()

if __name__ == "__main__":
    main()


