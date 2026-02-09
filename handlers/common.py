# handlers/common.py (ПОЛНАЯ ВЕРСИЯ С /start)

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from database import get_or_create_user, update_user

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    user = get_or_create_user(message.from_user.id, message.from_user.username or "NoUsername")
    if not user['started_chat']:
        update_user(message.from_user.id, started_chat=1)
    await message.answer(
        "Привет! 👋\n\n"
        "Теперь вы можете делать ставки в канале аукциона! 💰\n"
        "Нажмите кнопку ставки в посте с лотом. 🤑\n"
        "Напишите команду /status для просмотра своей статистики\n\n"
        "Удачи на аукционах! 🚀"
    )

@router.message(Command("status"))
async def cmd_status(message: Message):
    user = get_or_create_user(message.from_user.id, message.from_user.username or "NoUsername")
    text = (
        f"{message.from_user.first_name}, твоя статистика по аукционам  🔥\n\n"
        f"БАН: {'да 😈' if user['banned'] else 'нет ✅'}\n"
        f"Пауза: нет\n"
        f"📈 Всего сделано ставок: {user['total_bids']} \n"
        f"🏆 Выигранных аукционов: {user['won_auctions']} \n"
        f"⚠️ Отменённых ставок: {user['canceled_bids']} "
    )
    await message.answer(text)