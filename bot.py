import logging
import asyncio
from datetime import datetime
from typing import Dict, Optional
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import sqlite3
import os
import keep_alive

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = "7889278101:AAEYtujsGbLJ-A8zFtux3oNZV6H0bQoABNE"
ADMIN_GROUP_ID = --1002837608854  # ID группы администраторов
ADMIN_USER_IDS = [521620770, 987654321]  # ID администраторов

# Создаем бота и диспетчер
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# Состояния FSM
class SupportStates(StatesGroup):
    waiting_for_question = State()
    active_ticket = State()


class SupportBot:
    def __init__(self):
        self.db_path = "support_tickets.db"
        self.active_tickets: Dict[int, dict] = {}
        self.channel_to_user: Dict[int, int] = {}
        self.init_database()

    def init_database(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                channel_id INTEGER,
                channel_name TEXT,
                question TEXT,
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                from_user_id INTEGER,
                message_text TEXT,
                message_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ticket_id) REFERENCES tickets (id)
            )
        """)

        conn.commit()
        conn.close()

    def save_ticket(self, user_id: int, username: str, first_name: str, last_name: str,
                    channel_id: int, channel_name: str, question: str) -> int:
        """Сохранение тикета в базу данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO tickets (user_id, username, first_name, last_name, channel_id, channel_name, question)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, username, first_name, last_name, channel_id, channel_name, question))

        ticket_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return ticket_id

    def save_message(self, ticket_id: int, from_user_id: int, message_text: str, message_type: str):
        """Сохранение сообщения в базу данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO messages (ticket_id, from_user_id, message_text, message_type)
            VALUES (?, ?, ?, ?)
        """, (ticket_id, from_user_id, message_text, message_type))

        conn.commit()
        conn.close()

    def get_ticket_by_channel(self, channel_id: int) -> Optional[dict]:
        """Получение тикета по ID канала"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, user_id, username, first_name, last_name, channel_id, channel_name, question, status
            FROM tickets WHERE channel_id = ? AND status = 'open'
        """, (channel_id,))

        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                'id': result[0],
                'user_id': result[1],
                'username': result[2],
                'first_name': result[3],
                'last_name': result[4],
                'channel_id': result[5],
                'channel_name': result[6],
                'question': result[7],
                'status': result[8]
            }
        return None

    def get_ticket_by_user(self, user_id: int) -> Optional[dict]:
        """Получение активного тикета пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, user_id, username, first_name, last_name, channel_id, channel_name, question, status
            FROM tickets WHERE user_id = ? AND status = 'open'
        """, (user_id,))

        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                'id': result[0],
                'user_id': result[1],
                'username': result[2],
                'first_name': result[3],
                'last_name': result[4],
                'channel_id': result[5],
                'channel_name': result[6],
                'question': result[7],
                'status': result[8]
            }
        return None

    def close_ticket(self, ticket_id: int):
        """Закрытие тикета"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE tickets SET status = 'closed', closed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (ticket_id,))

        conn.commit()
        conn.close()


# Создаем экземпляр бота
support_bot = SupportBot()


@dp.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext):
    """Обработчик команды /start"""
    await state.clear()
    await message.answer(
        "Добро пожаловать в службу технической поддержки!\n\n"
        "Опишите вашу проблему или задайте вопрос, и наши специалисты свяжутся с вами в ближайшее время."
    )


@dp.message(Command("stats"))
async def admin_stats(message: types.Message):
    """Статистика для администраторов"""
    if message.from_user.id not in ADMIN_USER_IDS:
        return

    conn = sqlite3.connect(support_bot.db_path)
    cursor = conn.cursor()

    # Получаем статистику
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'open'")
    open_tickets = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'closed'")
    closed_tickets = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM tickets WHERE DATE(created_at) = DATE('now')")
    today_tickets = cursor.fetchone()[0]

    conn.close()

    stats_text = f"📊 <b>Статистика поддержки:</b>\n\n" \
                 f"🟢 Открытых тикетов: {open_tickets}\n" \
                 f"✅ Закрытых тикетов: {closed_tickets}\n" \
                 f"📅 Создано сегодня: {today_tickets}"

    await message.answer(stats_text, parse_mode='HTML')


@dp.message(F.chat.type == "private")
async def handle_user_message(message: types.Message, state: FSMContext):
    """Обработка сообщений от пользователей в приватном чате"""
    user = message.from_user
    message_text = message.text

    # Проверяем, есть ли уже активный тикет для этого пользователя
    active_ticket = support_bot.get_ticket_by_user(user.id)

    if active_ticket:
        # Пересылаем сообщение в группу поддержки
        try:
            await bot.send_message(
                chat_id=ADMIN_GROUP_ID,
                text=f"💬 <b>Сообщение от пользователя (тикет #{active_ticket['id']}):</b>\n"
                     f"👤 {user.first_name or ''} {user.last_name or ''}"
                     f"{' (@' + user.username + ')' if user.username else ''}\n"
                     f"🆔 ID: {user.id}\n\n"
                     f"📝 {message_text}",
                parse_mode='HTML'
            )

            # Сохраняем сообщение в базу данных
            support_bot.save_message(active_ticket['id'], user.id, message_text, 'user_message')

            await message.answer("Ваше сообщение отправлено в службу поддержки.")

        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения в группу: {e}")
            await message.answer("Произошла ошибка при отправке сообщения.")
    else:
        # Создаем новый тикет
        await create_new_ticket(message, message_text)


async def create_new_ticket(message: types.Message, question: str):
    """Создание нового тикета поддержки"""
    user = message.from_user

    # Создаем имя канала
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    channel_name = f"support_{user.id}_{timestamp}"

    try:
        # Создаем клавиатуру для администраторов
        keyboard = InlineKeyboardBuilder()
        keyboard.add(InlineKeyboardButton(
            text="📋 Взять в работу",
            callback_data=f"take_{user.id}"
        ))
        keyboard.add(InlineKeyboardButton(
            text="❌ Закрыть тикет",
            callback_data=f"close_{user.id}"
        ))
        keyboard.adjust(1)

        # Информация о пользователе
        user_info = f"👤 <b>Пользователь:</b> {user.first_name or ''} {user.last_name or ''}"
        if user.username:
            user_info += f" (@{user.username})"
        user_info += f"\n🆔 <b>ID:</b> {user.id}"

        # Отправляем информацию о новом тикете в группу администраторов
        admin_message = await bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=f"🎫 <b>Новый тикет поддержки #{timestamp}</b>\n\n"
                 f"{user_info}\n\n"
                 f"❓ <b>Вопрос:</b>\n{question}",
            parse_mode='HTML',
            reply_markup=keyboard.as_markup()
        )

        # Сохраняем тикет в базу данных
        ticket_id = support_bot.save_ticket(
            user.id, user.username, user.first_name, user.last_name,
            ADMIN_GROUP_ID, channel_name, question
        )

        # Сохраняем активный тикет в памяти
        support_bot.active_tickets[ticket_id] = {
            'id': ticket_id,
            'user_id': user.id,
            'channel_id': ADMIN_GROUP_ID,
            'channel_name': channel_name,
            'admin_message_id': admin_message.message_id,
            'question': question
        }

        support_bot.channel_to_user[ADMIN_GROUP_ID] = user.id

        await message.answer(
            "✅ Ваш запрос принят в обработку!\n"
            f"Номер тикета: #{timestamp}\n\n"
            "Ожидайте ответа от специалиста службы поддержки."
        )

    except Exception as e:
        logger.error(f"Ошибка при создании тикета: {e}")
        await message.answer(
            "Произошла ошибка при создании тикета. Попробуйте позже."
        )


@dp.message(F.chat.type.in_(["group", "supergroup"]))
async def handle_admin_response(message: types.Message):
    """Обработка ответов администраторов в группе"""
    # Проверяем, что сообщение в группе администраторов
    if message.chat.id != ADMIN_GROUP_ID:
        return

    # Проверяем, что отправитель - администратор
    if message.from_user.id not in ADMIN_USER_IDS:
        return

    # Проверяем, что это ответ на сообщение
    if not message.reply_to_message:
        return

    # Ищем тикет по тексту сообщения (извлекаем ID пользователя)
    original_text = message.reply_to_message.text
    if not original_text:
        return

    try:
        # Извлекаем ID пользователя из текста
        if "🆔 ID:" in original_text:
            user_id_line = [line for line in original_text.split('\n') if "🆔 ID:" in line][0]
            user_id = int(user_id_line.split("🆔 ID: ")[1])
        else:
            return

        # Находим активный тикет
        ticket = support_bot.get_ticket_by_user(user_id)
        if not ticket:
            await message.reply("❌ Тикет не найден или уже закрыт")
            return

        response_text = message.text

        # Отправляем ответ пользователю
        await bot.send_message(
            chat_id=user_id,
            text=f"👨‍💻 <b>Ответ службы поддержки:</b>\n\n{response_text}",
            parse_mode='HTML'
        )

        # Сохраняем ответ в базу данных
        support_bot.save_message(ticket['id'], message.from_user.id, response_text, 'admin_response')

        # Подтверждение для администратора
        await message.reply("✅ Ответ отправлен пользователю")

    except Exception as e:
        logger.error(f"Ошибка при обработке ответа администратора: {e}")
        await message.reply("❌ Ошибка при отправке ответа")


@dp.callback_query(F.data.startswith("take_"))
async def handle_take_ticket(callback: CallbackQuery):
    """Обработка взятия тикета в работу"""
    user_id = int(callback.data.split("_")[1])

    # Находим активный тикет
    ticket = support_bot.get_ticket_by_user(user_id)

    if ticket:
        # Обновляем сообщение
        await callback.message.edit_text(
            text=f"{callback.message.text}\n\n"
                 f"👨‍💻 <b>Взято в работу:</b> {callback.from_user.first_name}",
            parse_mode='HTML'
        )

        # Уведомляем пользователя
        await bot.send_message(
            chat_id=user_id,
            text=f"👨‍💻 Ваш запрос взят в работу специалистом {callback.from_user.first_name}.\n"
                 "Ожидайте ответа."
        )

        await callback.answer("✅ Тикет взят в работу")
    else:
        await callback.answer("❌ Тикет не найден", show_alert=True)


@dp.callback_query(F.data.startswith("close_"))
async def handle_close_ticket(callback: CallbackQuery):
    """Обработка закрытия тикета"""
    user_id = int(callback.data.split("_")[1])

    # Находим активный тикет
    ticket = support_bot.get_ticket_by_user(user_id)

    if ticket:
        # Закрываем тикет в базе данных
        support_bot.close_ticket(ticket['id'])

        # Удаляем из активных тикетов
        if ticket['id'] in support_bot.active_tickets:
            del support_bot.active_tickets[ticket['id']]

        # Обновляем сообщение
        await callback.message.edit_text(
            text=f"{callback.message.text}\n\n"
                 f"❌ <b>Тикет закрыт:</b> {callback.from_user.first_name}",
            parse_mode='HTML'
        )

        # Уведомляем пользователя
        await bot.send_message(
            chat_id=user_id,
            text="✅ Ваш запрос закрыт.\n"
                 "Спасибо за обращение! Если у вас есть другие вопросы, "
                 "отправьте новое сообщение."
        )

        await callback.answer("✅ Тикет закрыт")
    else:
        await callback.answer("❌ Тикет не найден", show_alert=True)


async def main():
    """Основная функция запуска бота"""
    logger.info("Бот запускается...")

    # Пропускаем накопившиеся апдейты
    await bot.delete_webhook(drop_pending_updates=True)

    # Запускаем polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    keep_alive.keep_alive()
    asyncio.run(main())