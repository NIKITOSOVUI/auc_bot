# handlers/auction.py (ПОЛНАЯ ВЕРСИЯ С ПРОВЕРКОЙ started_chat)

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
from database import (
    get_auction_by_id, get_or_create_user, update_user, make_bid,
    cancel_bid, get_user_last_bid, update_auction, get_bid_by_id
)
from config import CHANNEL_ID

router = Router()

def get_auction_caption(auction: dict) -> str:
    return (
        f"<b>🏷️ {auction['name']}</b>\n\n"
        f"{auction.get('description', '')}\n\n"
        f"💰 Стартовая цена: {auction['start_price']} руб\n"
        f"📈 Текущая цена: {auction['current_price']} руб\n"
        f"➕ Шаг ставки: {auction['step']} руб\n"
        f"🔢 Количество ставок: {auction['bids_count']}"
    )

def get_auction_keyboard(auction: dict) -> InlineKeyboardMarkup:
    next_bid = auction['current_price'] + auction['step']
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⌛️ Время до конца", callback_data=f"time|{auction['id']}")],
        [InlineKeyboardButton(text=f"💰 Сделать ставку: {next_bid} руб", callback_data=f"bid|{auction['id']}|{next_bid}")]
    ])

@router.callback_query(F.data.startswith("time|"))
async def show_time(callback: CallbackQuery):
    auction_id = int(callback.data.split("|")[1])
    auction = get_auction_by_id(auction_id)
    if not auction or auction['status'] != 'active':
        await callback.answer("❌ Аукцион завершён или отменён!", show_alert=True)
        return

    remaining = 7200 - (datetime.now().timestamp() - auction['last_bid_time'])
    if remaining <= 0:
        await callback.answer("⏰ Время вышло!", show_alert=True)
        return

    hours = int(remaining // 3600)
    mins = int((remaining % 3600) // 60)
    secs = int(remaining % 60)
    await callback.answer(f"⌛️ Осталось: {hours:02d}:{mins:02d}:{secs:02d}", show_alert=True)

@router.callback_query(F.data.startswith("bid|"))
async def process_bid(callback: CallbackQuery):
    from main import bot

    parts = callback.data.split("|")
    auction_id = int(parts[1])
    proposed = int(parts[2])

    auction = get_auction_by_id(auction_id)
    if not auction or auction['status'] != 'active':
        await callback.answer("❌ Аукцион не активен!", show_alert=True)
        return

    if proposed != auction['current_price'] + auction['step']:
        await callback.answer("🔄 Ставка устарела — обновите сообщение!", show_alert=True)
        return

    user = get_or_create_user(callback.from_user.id, callback.from_user.username or "NoUsername")

    if user['banned']:
        await callback.answer("🚫 Вы забанены!", show_alert=True)
        return

    if not user['started_chat']:
        await callback.answer("Сначала напишите боту /start в ЛС, чтобы делать ставки!", show_alert=True)
        return

    last_bid = get_user_last_bid(auction['id'], user['user_id'])
    if last_bid and (datetime.now().timestamp() - last_bid['timestamp'] < 120):
        await callback.answer("⏳ У вас уже есть активная ставка (2 минуты на отмену)!", show_alert=True)
        return

    bid_id = make_bid(auction['id'], user['user_id'], proposed)
    update_user(user['user_id'], total_bids=user['total_bids'] + 1)

    update_auction(
        auction['id'],
        current_price=proposed,
        last_bid_time=datetime.now().timestamp(),
        bids_count=auction['bids_count'] + 1
    )

    auction = get_auction_by_id(auction['id'])

    await bot.edit_message_caption(
        chat_id=CHANNEL_ID,
        message_id=auction['channel_message_id'],
        caption=get_auction_caption(auction),
        reply_markup=get_auction_keyboard(auction)
    )

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить ставку", callback_data=f"cancel|{bid_id}|1")]
    ])

    await bot.send_message(
        callback.from_user.id,
        f"👋 Дружище {callback.from_user.first_name}! 🎉 Ваша ставка {proposed} руб принята! 💰\n\n"
        f"🏆 Если в течение 120 минут её не перебьют — лот ваш! 🏅\n\n"
        f"⚠️ Если ошибка — у вас 2 минуты на отмену (двойное нажатие)! ⏰\n"
        f"После 3 отмен — бан 🚫",
        reply_markup=cancel_kb
    )

    await callback.answer("✅ Ставка принята!")

@router.callback_query(F.data.startswith("cancel|"))
async def process_cancel(callback: CallbackQuery):
    from main import bot

    parts = callback.data.split("|")
    bid_id = int(parts[1])
    stage = int(parts[2])

    bid = get_bid_by_id(bid_id)
    if not bid or bid['canceled']:
        await callback.answer("❌ Ставка не найдена или уже отменена!", show_alert=True)
        return

    if bid['user_id'] != callback.from_user.id:
        await callback.answer("🔒 Это не ваша ставка!", show_alert=True)
        return

    if datetime.now().timestamp() - bid['timestamp'] > 120:
        await callback.answer("⏰ Время на отмену истекло!", show_alert=True)
        return

    auction = get_auction_by_id(bid['auction_id'])
    if not auction or auction['status'] != 'active':
        await callback.answer("❌ Аукцион не активен!", show_alert=True)
        return

    user = get_or_create_user(callback.from_user.id, callback.from_user.username or "NoUsername")

    if not user['started_chat']:
        await callback.answer("Сначала напишите боту /start в ЛС, чтобы отменять ставки!", show_alert=True)
        return

    if stage == 1:
        await callback.answer(
            "⚠️ Вы действительно хотите отменить ставку?\nНажмите ещё раз для подтверждения!",
            show_alert=True
        )

        confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить ставку", callback_data=f"cancel|{bid_id}|2")]
        ])
        await bot.edit_message_reply_markup(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            reply_markup=confirm_kb
        )
    else:
        cancel_bid(bid_id, auction['id'])

        new_canceled = user['canceled_bids'] + 1
        update_user(callback.from_user.id, canceled_bids=new_canceled)
        if new_canceled >= 3:
            update_user(callback.from_user.id, banned=1)

        auction = get_auction_by_id(auction['id'])

        await bot.edit_message_caption(
            chat_id=CHANNEL_ID,
            message_id=auction['channel_message_id'],
            caption=get_auction_caption(auction),
            reply_markup=get_auction_keyboard(auction)
        )

        status_text = (
            f"✅ Ставка отменена!\n\n"
            f"👋 Твой статус, дружище {callback.from_user.first_name}\n\n"
            f"🚫 БАН: {'да 😈' if user['banned'] else 'нет ✅'}\n"
            f"⏸ Пауза: нет\n"
            f"📊 Всего сделано ставок: {user['total_bids']}\n"
            f"🏆 Выигранных аукционов: {user['won_auctions']}\n"
            f"❌ Отменённых ставок: {user['canceled_bids']}"
        )

        await bot.edit_message_text(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            text=status_text,
            reply_markup=None
        )

        await callback.answer("✅ Ставка отменена.")