import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_NAME = 'todo.db'

def init_db():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        logger.info("Успішно підключено до бази даних SQLite")
        create_table_query = """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_text TEXT NOT NULL,
            deadline TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending'
        );
        """
        cursor.execute(create_table_query)
        conn.commit()
        logger.info("Таблицю tasks успішно створено (або вона вже існує)")

    except sqlite3.Error as e:
        logger.error(f"Помилка при роботі з SQLite: {e}")
    finally:
        if conn:
            conn.close()
            logger.info("З'єднання з SQLite закрито")

if __name__ == "__main__":
    init_db()