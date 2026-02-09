# handlers/admin.py (ПОЛНАЯ АКТУАЛЬНАЯ ВЕРСИЯ)

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from config import ADMIN_ID, CHANNEL_ID
from database import (
    create_auction, get_all_auctions, update_auction, get_auction_by_id,
    get_conn, get_bids_for_auction, get_or_create_user
)
from datetime import datetime

router = Router()

class NewAuction(StatesGroup):
    photo = State()
    name_price = State()
    description = State()
    preview = State()
    edit_name = State()
    edit_price = State()
    edit_step = State()

def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать новый аукцион", callback_data="admin_new_auction")],
        [InlineKeyboardButton(text="🟢 Активные аукционы", callback_data="admin_active")],
        [InlineKeyboardButton(text="🔴 Закрытые аукционы", callback_data="admin_ended")],
        [InlineKeyboardButton(text="❌ Отменённые аукционы", callback_data="admin_canceled")]
    ])

@router.message(Command("admin"), F.from_user.id.in_(ADMIN_ID))
async def cmd_admin(message: Message):
    active = len(get_all_auctions('active'))
    ended = len(get_all_auctions('ended'))
    canceled = len(get_all_auctions('canceled'))

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(DISTINCT user_id) FROM bids")
    unique_users = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM bids")
    total_bids = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM users WHERE banned = 1")
    banned_users = c.fetchone()[0] or 0
    conn.close()

    stats_text = (
        f"<b>📊 Статистика аукционов</b>\n\n"
        f"🟢 Активных: {active}\n"
        f"🔴 Завершённых: {ended}\n"
        f"❌ Отменённых: {canceled}\n\n"
        f"👥 Участников: {unique_users}\n"
        f"💰 Всего ставок: {total_bids}\n"
        f"🚫 Забаненных: {banned_users}\n\n"
        f"👇 Админ-панель:"
    )

    await message.answer(stats_text, reply_markup=get_admin_keyboard())

def get_preview_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить название", callback_data="edit_name"),
         InlineKeyboardButton(text="💸 Изменить цену", callback_data="edit_price")],
        [InlineKeyboardButton(text="➕ Изменить шаг", callback_data="edit_step"),
         InlineKeyboardButton(text="📝 Изменить описание", callback_data="edit_desc")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_create"),
         InlineKeyboardButton(text="✅ Опубликовать", callback_data="publish")]
    ])

async def show_preview(callback_or_message, state: FSMContext):
    from main import bot

    data = await state.get_data()
    step = data.get('step', 500)
    current_price = data['start_price']
    next_bid = current_price + step

    caption = (
        f"<b>🏷️ {data['name']}</b>\n\n"
        f"{data.get('description', '')}\n\n"
        f"💰 Стартовая цена: {data['start_price']} руб\n"
        f"📈 Текущая цена: {current_price} руб\n"
        f"➕ Шаг ставки: {step} руб\n"
        f"🔢 Количество ставок: 0"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⌛️ Время до конца", callback_data="noop")],
        [InlineKeyboardButton(text=f"💰 Сделать ставку: {next_bid} руб", callback_data="noop")]
    ])

    preview_msg_id = data.get('preview_message_id')

    chat_id = callback_or_message.from_user.id if isinstance(callback_or_message, Message) else callback_or_message.message.chat.id

    if preview_msg_id:
        try:
            await bot.edit_message_caption(
                chat_id=chat_id,
                message_id=preview_msg_id,
                caption=caption,
                reply_markup=keyboard
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise
    else:
        sent = await bot.send_photo(
            chat_id=chat_id,
            photo=data['photo_file_id'],
            caption=caption,
            reply_markup=keyboard
        )
        await state.update_data(preview_message_id=sent.message_id)

    control_msg_id = data.get('control_message_id')
    if control_msg_id:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=control_msg_id,
                text="👆 Превью аукциона выше. Измените или опубликуйте:",
                reply_markup=get_preview_keyboard()
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise
    else:
        sent_control = await bot.send_message(
            chat_id=chat_id,
            text="👆 Превью аукциона выше. Измените или опубликуйте:",
            reply_markup=get_preview_keyboard()
        )
        await state.update_data(control_message_id=sent_control.message_id)

@router.callback_query(F.data == "admin_new_auction")
async def admin_new_auction(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📸 Отправьте фото лота.")
    await state.set_state(NewAuction.photo)

@router.message(NewAuction.photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    photo_file_id = message.photo[-1].file_id
    await state.update_data(photo_file_id=photo_file_id, step=500)
    await message.answer("🏷️ Введите название и стартовую цену (пример: Триммер 3500)")
    await state.set_state(NewAuction.name_price)

@router.message(NewAuction.name_price)
async def process_name_price(message: Message, state: FSMContext):
    try:
        name, price_str = message.text.rsplit(maxsplit=1)
        price = int(price_str)
        await state.update_data(name=name.strip(), start_price=price)
        await message.answer("📝 Введите описание лота (или /skip):")
        await state.set_state(NewAuction.description)
    except:
        await message.answer("❌ Неверный формат. Нужно название и цена через пробел.")

@router.message(NewAuction.description)
async def process_description(message: Message, state: FSMContext):
    description = message.text if message.text != "/skip" else ""
    await state.update_data(description=description)
    await show_preview(message, state)
    await state.set_state(NewAuction.preview)

async def confirm_edit_and_cleanup(message: Message, state: FSMContext, field_name: str):
    from main import bot

    data = await state.get_data()
    request_msg_id = data.get('request_message_id')
    if request_msg_id:
        try:
            await bot.delete_message(chat_id=message.from_user.id, message_id=request_msg_id)
        except TelegramBadRequest:
            pass
    try:
        await bot.delete_message(chat_id=message.from_user.id, message_id=message.message_id)
    except TelegramBadRequest:
        pass

    await message.answer(f"✅ {field_name} изменено!")
    await show_preview(message, state)
    await state.set_state(NewAuction.preview)
    await state.update_data(request_message_id=None)

@router.message(NewAuction.edit_name)
async def process_edit_name(message: Message, state: FSMContext):
    new_name = message.text.strip()
    if not new_name:
        await message.answer("❌ Название не может быть пустым.")
        return
    await state.update_data(name=new_name)
    await confirm_edit_and_cleanup(message, state, "Название")

@router.message(NewAuction.edit_price)
async def process_edit_price(message: Message, state: FSMContext):
    try:
        new_price = int(message.text.strip())
        if new_price < 1:
            raise ValueError
        await state.update_data(start_price=new_price)
        await confirm_edit_and_cleanup(message, state, "Цена")
    except:
        await message.answer("❌ Неверный формат. Введите только число (новая цена).")

@router.message(NewAuction.edit_step)
async def process_edit_step(message: Message, state: FSMContext):
    try:
        new_step = int(message.text.strip())
        if new_step < 50:
            await message.answer("❌ Шаг слишком маленький. Минимум 50 руб.")
            return
        await state.update_data(step=new_step)
        await confirm_edit_and_cleanup(message, state, "Шаг ставки")
    except:
        await message.answer("❌ Неверный формат. Введите только число (новый шаг).")

@router.message(NewAuction.description, NewAuction.preview)
async def process_edit_description(message: Message, state: FSMContext):
    description = message.text if message.text != "/skip" else ""
    await state.update_data(description=description)
    await confirm_edit_and_cleanup(message, state, "Описание")

@router.callback_query(F.data.in_({"edit_name", "edit_price", "edit_step", "edit_desc"}), NewAuction.preview)
async def edit_field(callback: CallbackQuery, state: FSMContext):
    from main import bot

    mapping = {
        "edit_name": ("✏️ Введите новое название лота:", NewAuction.edit_name),
        "edit_price": ("💸 Введите новую стартовую цену:", NewAuction.edit_price),
        "edit_step": ("➕ Введите новый шаг ставки:", NewAuction.edit_step),
        "edit_desc": ("📝 Введите новое описание (или /skip):", NewAuction.description)
    }
    text, new_state = mapping[callback.data]

    sent = await callback.message.answer(text)
    await state.update_data(request_message_id=sent.message_id)

    data = await state.get_data()
    control_msg_id = data.get('control_message_id')
    if control_msg_id:
        try:
            await bot.edit_message_reply_markup(
                chat_id=callback.from_user.id,
                message_id=control_msg_id,
                reply_markup=None
            )
        except TelegramBadRequest:
            pass

    await state.set_state(new_state)

@router.callback_query(F.data == "cancel_create", NewAuction.preview)
async def cancel_create(callback: CallbackQuery, state: FSMContext):
    from main import bot
    data = await state.get_data()
    preview_msg_id = data.get('preview_message_id')
    control_msg_id = data.get('control_message_id')
    if preview_msg_id:
        try:
            await bot.delete_message(chat_id=callback.from_user.id, message_id=preview_msg_id)
        except TelegramBadRequest:
            pass
    if control_msg_id:
        try:
            await bot.delete_message(chat_id=callback.from_user.id, message_id=control_msg_id)
        except TelegramBadRequest:
            pass
    await state.clear()
    await callback.message.answer("❌ Создание аукциона отменено.", reply_markup=get_admin_keyboard())

@router.callback_query(F.data == "publish", NewAuction.preview)
async def publish_auction(callback: CallbackQuery, state: FSMContext):
    from main import bot

    data = await state.get_data()

    step = data.get('step', 500)
    current_price = data['start_price']
    next_bid = current_price + step

    caption = (
        f"<b>🏷️ {data['name']}</b>\n\n"
        f"{data.get('description', '')}\n\n"
        f"💰 Стартовая цена: {data['start_price']} руб\n"
        f"📈 Текущая цена: {current_price} руб\n"
        f"➕ Шаг ставки: {step} руб\n"
        f"🔢 Количество ставок: 0"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⌛️ Время до конца", callback_data="time|0")],
        [InlineKeyboardButton(text=f"💰 Сделать ставку: {next_bid} руб", callback_data=f"bid|0|{next_bid}")]
    ])

    sent = await bot.send_photo(
        chat_id=CHANNEL_ID,
        photo=data['photo_file_id'],
        caption=caption,
        reply_markup=keyboard
    )

    auction_id = create_auction(
        channel_message_id=sent.message_id,
        photo_file_id=data['photo_file_id'],
        name=data['name'],
        description=data.get('description', ''),
        start_price=current_price,
        current_price=current_price,
        step=step,
        last_bid_time=datetime.now().timestamp(),
        bids_count=0,
        status='active'
    )

    updated_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⌛️ Время до конца", callback_data=f"time|{auction_id}")],
        [InlineKeyboardButton(text=f"💰 Сделать ставку: {next_bid} руб", callback_data=f"bid|{auction_id}|{next_bid}")]
    ])

    await bot.edit_message_reply_markup(
        chat_id=str(CHANNEL_ID),
        message_id=sent.message_id,
        reply_markup=updated_keyboard
    )

    preview_msg_id = data.get('preview_message_id')
    control_msg_id = data.get('control_message_id')
    if preview_msg_id:
        try:
            await bot.delete_message(chat_id=callback.from_user.id, message_id=preview_msg_id)
        except TelegramBadRequest:
            pass
    if control_msg_id:
        try:
            await bot.delete_message(chat_id=callback.from_user.id, message_id=control_msg_id)
        except TelegramBadRequest:
            pass

    await callback.message.answer("✅ Аукцион опубликован!", reply_markup=get_admin_keyboard())
    await state.clear()

def get_filter_keyboard(status):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Сегодня", callback_data=f"filter_{status}_1"),
         InlineKeyboardButton(text="🗓️ 3 дня", callback_data=f"filter_{status}_3")],
        [InlineKeyboardButton(text="📆 Неделя", callback_data=f"filter_{status}_7"),
         InlineKeyboardButton(text="🗓️ Месяц", callback_data=f"filter_{status}_30")],
        [InlineKeyboardButton(text="🔙 Назад в админ-панель", callback_data="admin_back")]
    ])

@router.callback_query(F.data.in_({"admin_active", "admin_ended", "admin_canceled"}))
async def list_auctions(callback: CallbackQuery):
    status_map = {
        "admin_active": ("active", "🟢 Активные аукционы"),
        "admin_ended": ("ended", "🔴 Закрытые аукционы"),
        "admin_canceled": ("canceled", "❌ Отменённые аукционы")
    }
    status, title = status_map[callback.data]
    if status == 'active':
        auctions = get_all_auctions(status)
        await show_auction_list(callback, auctions, title, status)
    else:
        try:
            await callback.message.edit_text(f"{title}: выберите фильтр по дате 📅", reply_markup=get_filter_keyboard(status))
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise

@router.callback_query(F.data.regexp(r"filter_(ended|canceled)_(\d+)"))
async def filtered_list(callback: CallbackQuery):
    parts = callback.data.split("_")
    status = parts[1]
    days = int(parts[2])
    title = "🔴 Закрытые аукционы" if status == "ended" else "❌ Отменённые аукционы"
    auctions = get_all_auctions(status, days if days > 0 else None)
    await show_auction_list(callback, auctions, title, status)

async def show_auction_list(callback, auctions, title, status):
    kb = []
    if not auctions:
        back_callback = f"admin_{status}" if status != 'active' else "admin_back"
        kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback)])
        try:
            await callback.message.edit_text(f"{title}: нет", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise
        return

    for a in auctions:
        info = f"{a['name']} | {a['current_price']}₽ | ставок: {a['bids_count']}"
        if status == 'active':
            kb.append([InlineKeyboardButton(text=f"❌ Отменить: {info}", callback_data=f"admin_cancel|{a['id']}")])
        else:
            kb.append([InlineKeyboardButton(text=info, callback_data=f"admin_view_bids|{a['id']}")])

    back_callback = f"admin_{status}" if status != 'active' else "admin_back"
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback)])
    try:
        await callback.message.edit_text(f"{title} ({len(auctions)}):", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise

@router.callback_query(F.data.startswith("admin_view_bids|"))
async def view_bids(callback: CallbackQuery):
    auction_id = int(callback.data.split("|")[1])
    auction = get_auction_by_id(auction_id)
    bids = get_bids_for_auction(auction_id)

    if not bids:
        text = "Ставок нет."
    else:
        text_lines = [f"<b>💰 Ставки в аукционе \"{auction['name']}\"</b>\n"]
        for b in bids:
            username = f"@{b['username']}" if b['username'] and b['username'] != "NoUsername" else f"ID: {b['user_id']}"
            status = " (отменена)" if b['canceled'] else ""
            text_lines.append(f"{username} — {b['amount']} руб{status}")
        text = "\n".join(text_lines)

    back_data = f"admin_{auction['status']}" if auction['status'] != 'active' else "admin_back"
    kb = [[InlineKeyboardButton(text="🔙 Назад", callback_data=back_data)]]
    try:
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise

@router.callback_query(F.data.startswith("admin_cancel|"))
async def cancel_auction(callback: CallbackQuery):
    from main import bot

    auction_id = int(callback.data.split("|")[1])
    auction = get_auction_by_id(auction_id)
    update_auction(auction_id, status='canceled')

    try:
        await bot.edit_message_caption(
            chat_id=str(CHANNEL_ID),
            message_id=auction['channel_message_id'],
            caption=f"{auction['name']} — АУКЦИОН ОТМЕНЁН АДМИНОМ",
            reply_markup=None
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise

    await callback.answer("❌ Аукцион отменён.")
    await cmd_admin(callback.message)

@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    await cmd_admin(callback.message)