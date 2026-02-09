from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import BOT_TOKEN
from database import init_db
from handlers import routers
from utils.auction_scheduler import start_scheduler


bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

async def on_startup():
    init_db()
    start_scheduler()
    print("Бот запущен")

def main():
    for router in routers:
        dp.include_router(router)
    
    dp.startup.register(on_startup)  # Регистрация без параметров
    dp.run_polling(bot)

if __name__ == "__main__":
    main()