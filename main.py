import logging
import os
from http.client import responses
import dateparser
from datetime import datetime, timedelta

from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    #for dialog
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler
    )

from database import init_db, add_task, get_tasks, mark_task_done, delete_task_db, get_single_task, update_task_text, update_task_deadline, get_all_pending_tasks_with_deadline, set_reminder_sent

load_dotenv()
TOKEN = os.getenv("TG_TOKEN")
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

GET_TASK_TEXT, GET_DEADLINE = range(2)
EDIT_MENU, EDIT_GET_TEXT, EDIT_GET_DEADLINE = range(2, 5)

MAIN_KEYBOARD_LAYOUT = [
    ["Нове завдання 📝"],
    ["Список завдань 📋"],
]
MAIN_KEYBOARD_MARKUP = ReplyKeyboardMarkup(
    MAIN_KEYBOARD_LAYOUT,
    resize_keyboard=True,
)

#Logic bot

def parse_date(date_string):
    return dateparser.parse(date_string, settings={'PREFER_DATES_FROM': 'future'})

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        f"Здоров, {user.first_name}! \n\n"
        f"Я твій особистий планер задач. "
        f"Обирай що хочеш зробити",
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
    user_input = update.message.text
    user = update.effective_user

    parsed_date = parse_date(user_input)

    if not parsed_date:
        await update.message.reply_text(
            "❌ Не можу зрозуміти цю дату.\n"
            "Спробуйте формат: <i>25.12.2025 15:00</i> або <i>Завтра о 9 вечора</i>",
            parse_mode="HTML"
        )
        return GET_DEADLINE

    if parsed_date < datetime.now():
        await update.message.reply_text(
            "⏳ Ця дата вже минула! Введіть майбутній час.",
        )
        return GET_DEADLINE

    formatted_date = parsed_date.strftime('%Y-%m-%d %H:%M:%S')

    task_text = context.user_data["current_task_text"]
    add_task(user.id, task_text, formatted_date)

    await update.message.reply_text(
        f"✅ Завдання додано:\n"
        f"<b>{task_text}</b>\n"
        f"⏰ Дедлайн: {formatted_date}",
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

async def edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    _, _, task_id_str = query.data.split(":")
    task_id = int(task_id_str)
    user_id = query.from_user.id

    task = get_single_task(user_id, task_id)
    if not task:
        await query.message.reply_text("Помилка: це завдання вже не існує.")
        return ConversationHandler.END

    context.user_data['edit_task_id'] = task_id

    keyboard = [
        [
            InlineKeyboardButton(
                "✏️ Текст",
                callback_data=f"edit:text:{task_id}"
            ),
            InlineKeyboardButton(
                "📅 Дедлайн",
                callback_data=f"edit:deadline:{task_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                "⬅️ Назад до списку",
                callback_data="edit:cancel"
            )
        ]
    ]

    await query.edit_message_text(
        text=f"<b>Редагування завдання:</b>\n{task['task_text']}\n"
             f"<i>Дедлайн: {task['deadline'] or 'немає'}</i>\n\n"
             "Що хочете змінити?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

    return EDIT_MENU

async def edit_text_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "Надішли мені <b>новий текст</b> для цього завдання "
        "(або /cancel для скасування).",
        parse_mode="HTML"
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

async def edit_deadline_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    reply_keyboard = [["Видалити дедлайн"]]
    await query.message.reply_text(
        "Надішли мені <b>новий дедлайн</b> (наприклад, 'завтра о 10')\n"
        "або натисни 'Видалити дедлайн' (чи /cancel).",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
        parse_mode="HTML"
    )
    return EDIT_GET_DEADLINE


async def edit_receive_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    user_input = update.message.text

    parsed_date = parse_date(user_input)

    if not parsed_date:
        await update.message.reply_text("❌ Незрозуміла дата. Спробуйте ще раз.")
        return EDIT_GET_DEADLINE

    if parsed_date < datetime.now():
        await update.message.reply_text("⏳ Дата в минулому! Спробуйте ще раз.")
        return EDIT_GET_DEADLINE

    formatted_date = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
    task_id = context.user_data['edit_task_id']

    update_task_text(user.id, task_id, formatted_date)

    await update.message.reply_text(
        f"✅ Дедлайн оновлено на: {formatted_date}",
        reply_markup=MAIN_KEYBOARD_MARKUP
    )
    context.user_data.clear()
    return ConversationHandler.END

async def check_deadlines(context: ContextTypes.DEFAULT_TYPE):
    tasks = get_all_pending_tasks_with_deadline()

    now = datetime.now()
    for task in tasks:
        try:
            deadline_str = task['deadline']
            deadline_dt = datetime.strptime(deadline_str, "%Y-%m-%d %H:%M:%S")

            time_left = deadline_dt - now
            if timedelta(minutes=0) < time_left <= timedelta(minutes=30):
                await context.bot.send_message(
                    chat_id=task['user_id'],
                    text=f"⏰ <b>НАГАДУВАННЯ!</b>\n\n"
                         f"Завдання: <b>{task['task_text']}</b>\n"
                         f"Дедлайн: {deadline_str} (залишилось менше 30 хв!)",
                    parse_mode="HTML"
                )

                set_reminder_sent(task['id'])

            elif time_left < timedelta(minutes=0):
                await context.bot.send_message(
                    char_id=task['user_id'],
                    text=f"🔥 <b>ДЕДЛАЙН ПРОСТРОЧЕНО!</b>\n\n"
                         f"Завдання: <b>{task['task_text']}</b>\n"
                         f"Мало бути виконано: {deadline_str}",
                    parse_mode="HTML"
                )
                set_reminder_sent(task['id'])

        except ValueError:
            continue


async def edit_remove_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    task_id = context.user_data['edit_task_id']
    update_task_deadline(user.id, task_id, None)

    await update.message.reply_text(
        f"✅ Дедлайн для завдання (ID: {task_id}) видалено.",
        reply_markup=MAIN_KEYBOARD_MARKUP
    )

    context.user_data.clear()
    return ConversationHandler.END


async def edit_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "Редагування скасовано.",
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

    await update.message.reply_text(
        "Ось ваші активні завдання:",
        reply_markup=MAIN_KEYBOARD_MARKUP
    )

    for task in tasks:
        task_id = task['id']
        task_text = task['task_text']
        deadline = task['deadline']

        message_text = f"<b>Завдання ID {task_id}:</b>\n{task_text}"
        if deadline:
            message_text += f"\n<i>Дедлайн: {deadline}</i>"

        keyboard_buttons = [
            InlineKeyboardButton(
                "✅ Виконати",
                callback_data=f"task:done:{task_id}"
            ),
            InlineKeyboardButton(
                "✏️ Редагувати",
                callback_data=f"task:edit:{task_id}"
            ),
            InlineKeyboardButton(
                "🗑️ Видалити",
                callback_data=f"task:del:{task_id}"
            ),
        ]
        keyboard = InlineKeyboardMarkup([keyboard_buttons])

        await update.message.reply_html(
            message_text,
            reply_markup=keyboard
        )

async def task_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    _, action, task_id_str = data.split(":")
    task_id = int(task_id_str)
    user_id = query.from_user.id
    original_text = query.message.text.split('\n', 1)[-1]

    if action == "done":
        rows_affected = mark_task_done(user_id, task_id)
        if rows_affected > 0:
            await query.edit_message_text(
                text=f"✅ <b>Виконано:</b>\n<s>{original_text}</s>",
                parse_mode="HTML"
            )
        else:
            await query.answer("Помилка: завдання не знайдено.")

    elif action == "del":
        rows_affected = delete_task_db(user_id, task_id)
        if rows_affected > 0:
            await query.edit_message_text(
                text=f"🗑️ <b>Видалено:</b>\n<s>{original_text}</s>",
                parse_mode="HTML"
            )
        else:
            await query.answer("Помилка: завдання не знайдено.")

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
            CallbackQueryHandler(
                edit_menu,
                pattern=r"^task:edit:\d+$"
            )
        ],
        states={
            EDIT_MENU: [
                CallbackQueryHandler(
                    edit_text_start,
                    pattern=r"^edit:text:\d+$"
                ),
                CallbackQueryHandler(
                    edit_deadline_start,
                    pattern=r"^edit:deadline:\d+$"
                ),
                CallbackQueryHandler(
                    edit_cancel,
                    pattern=r"^edit:cancel$"
                )
            ],
            EDIT_GET_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_receive_text)
            ],
            EDIT_GET_DEADLINE: [
                MessageHandler(filters.Regex("^Видалити дедлайн$"), edit_remove_deadline),
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_receive_deadline),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(edit_cancel, pattern=r"^edit:cancel$")
        ],
    )

    application.add_handler(new_conv_handler)
    application.add_handler(edit_conv_handler)
    #start
    application.add_handler(CommandHandler("start", start))
    #list
    application.add_handler(CommandHandler("list", list_tasks))
    application.add_handler(MessageHandler(filters.Regex("^Список завдань 📋$"), list_tasks))

    application.add_handler(CallbackQueryHandler(
        task_button_callback,
        pattern=r"^task:done:\d+$"
    ))
    application.add_handler(CallbackQueryHandler(
        task_button_callback,
        pattern=r"^task:del:\d+$"
    ))

    application.add_handler(CommandHandler("cancel", cancel))

    job_queue = application.job_queue
    job_queue.run_repeating(check_deadlines, interval=60, first=10)

    print("Бот запускається... Натисніть Ctrl+C для зупинки.")
    application.run_polling()


if __name__ == "__main__":
    main()


