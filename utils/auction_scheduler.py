from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from database import get_all_auctions, update_auction, get_auction_by_id

scheduler = AsyncIOScheduler()

async def check_auctions_end():
    from main import bot  # Локальный импорт
    from config import CHANNEL_ID

    active = get_all_auctions('active')
    for auction in active:
        if datetime.now().timestamp() - auction['last_bid_time'] > 7200:
            # Логика завершения (победитель, обновление статуса)
            update_auction(auction['id'], status='ended', winner_id=None)  # дополните поиск победителя

            await bot.edit_message_caption(
                chat_id=CHANNEL_ID,
                message_id=auction['channel_message_id'],
                caption=f"{auction['name']} — АУКЦИОН ЗАВЕРШЁН!\nФинальная цена: {auction['current_price']} руб",
                reply_markup=None
            )

def start_scheduler():
    scheduler.start()
    scheduler.add_job(check_auctions_end, 'interval', seconds=60)