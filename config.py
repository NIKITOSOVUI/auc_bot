import os
from dotenv import load_dotenv
from typing import List

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
ADMIN_IDS_STR = os.getenv("ADMIN_ID", "")
ADMIN_ID: List[int] = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip()]