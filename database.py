import sqlite3
import logging

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
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

def add_task(user_id: int, task_text: str, deadline: str = None) -> bool:
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        insert_query = "INSERT INTO tasks (user_id, task_text, deadline) VALUES (?, ?, ?)"
        cursor.execute(insert_query, (user_id, task_text, deadline))
        conn.commit()
        logger.info(f"Нове завдання додано для user_id {user_id} з дедлайном {deadline}")
        return True

    except sqlite3.Error as e:
        logger.error(f"Помилка при додаванні завдання: {e}")
        return False

    finally:
        if conn:
            conn.close()

def get_tasks(user_id: int) -> list:
    tasks = []
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        select_query = """
        SELECT id, task_text, deadline 
        FROM tasks 
        WHERE user_id = ? AND status = 'pending' 
        ORDER BY created_at ASC
        """

        cursor.execute(select_query, (user_id, ))
        tasks = cursor.fetchall()

    except sqlite3.Error as e:
        logger.error(f"Помилка при отриманні завдань: {e}")
    finally:
        if conn:
            conn.close()
    return tasks

def mark_task_done(user_id: int, task_id: int) -> int:
    row_count = 0
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        update_query = """
        UPDATE tasks 
        SET status = 'done' 
        WHERE id = ? AND user_id = ? AND status = 'pending'
        """
        cursor.execute(update_query, (task_id, user_id))
        conn.commit()
        row_count = cursor.rowcount

    except sqlite3.Error as e:
        logger.error(f"Помилка при оновленні завдання: {e}")
    finally:
        if conn:
            conn.close()
    return row_count

def delete_task_db(user_id: int, task_id: int) -> int:
    row_count = 0
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        delete_query = "DELETE FROM tasks WHERE id = ? AND user_id = ?"

        cursor.execute(delete_query, (task_id, user_id))
        conn.commit()
        row_count = cursor.rowcount
    except sqlite3.Error as e:
        logger.error(f"Помилка при видаленні завдання: {e}")
    finally:
        if conn:
            conn.close()

    return row_count

def get_single_task(user_id: int, task_id: int):
    task = None
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        select_query = "SELECT * FROM tasks WHERE id = ? AND user_id = ?"
        cursor.execute(select_query, (task_id, user_id))
        task = cursor.fetchone()
    except sqlite3.Error as e:
        logger.error(f"Помилка при отриманні одного завдання: {e}")
    finally:
        if conn:
            conn.close()
    return task

def update_task_text(user_id: int, task_id: int, new_text: str) -> bool:
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        update_query = """
        UPDATE tasks 
        SET task_text = ? 
        WHERE id = ? AND user_id = ?
        """

        cursor.execute(update_query, (new_text, task_id, user_id))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"Помилка при оновленні тексту завдання: {e}")
        return False
    finally:
        if conn:
            conn.close()

def update_task_deadline(user_id: int, task_id: int, new_deadline: str | None) -> bool:
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        update_query = """
        UPDATE tasks 
        SET deadline = ? 
        WHERE id = ? AND user_id = ?
        """
        cursor.execute(update_query, (new_deadline, task_id, user_id))
        conn.commit()

    except sqlite3.Error as e:
        logger.error(f"Помилка при оновленні дедлайну: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    init_db()