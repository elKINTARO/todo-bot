import logging
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackContext

from database import init_db, add_task

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

def main() -> None:
    #init db
    init_db()
    logger.info("Базу даних ініціалізовано")
    #create app
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new", new_task)) #create task
    print("Бот запускається... Натисніть Ctrl+C для зупинки.")
    application.run_polling()

if __name__ == "__main__":
    main()


