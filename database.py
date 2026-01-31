# database.py (ПОЛНАЯ АКТУАЛЬНАЯ ВЕРСИЯ С ПОЛЕМ started_chat)

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "db.sqlite"

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS auctions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_message_id INTEGER UNIQUE,
            photo_file_id TEXT,
            name TEXT,
            description TEXT,
            start_price INTEGER,
            current_price INTEGER,
            step INTEGER DEFAULT 500,
            last_bid_time REAL,
            created_at REAL,
            bids_count INTEGER DEFAULT 0,
            winner_id INTEGER,
            status TEXT DEFAULT 'active'
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            banned INTEGER DEFAULT 0,
            on_pause INTEGER DEFAULT 0,
            total_bids INTEGER DEFAULT 0,
            won_auctions INTEGER DEFAULT 0,
            canceled_bids INTEGER DEFAULT 0,
            started_chat INTEGER DEFAULT 0
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS bids (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            auction_id INTEGER,
            user_id INTEGER,
            amount INTEGER,
            timestamp REAL,
            canceled INTEGER DEFAULT 0
        )
    ''')
    
    # Миграция для created_at
    c.execute("PRAGMA table_info(auctions)")
    columns = [info[1] for info in c.fetchall()]
    if 'created_at' not in columns:
        c.execute("ALTER TABLE auctions ADD COLUMN created_at REAL")
        current_time = datetime.now().timestamp()
        c.execute("UPDATE auctions SET created_at = COALESCE(last_bid_time, ?) WHERE created_at IS NULL", (current_time,))
    
    # Миграция для started_chat
    c.execute("PRAGMA table_info(users)")
    columns = [info[1] for info in c.fetchall()]
    if 'started_chat' not in columns:
        c.execute("ALTER TABLE users ADD COLUMN started_chat INTEGER DEFAULT 0")
    
    conn.commit()
    conn.close()

def get_all_auctions(status=None, days=None):
    conn = get_conn()
    c = conn.cursor()
    query = "SELECT * FROM auctions"
    params = []
    conditions = []
    if status:
        conditions.append("status = ?")
        params.append(status)
    if days is not None and days > 0:
        timestamp = datetime.now().timestamp() - days * 86400
        conditions.append("created_at >= ?")
        params.append(timestamp)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC"
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    if rows:
        columns = [desc[0] for desc in c.description]
        return [dict(zip(columns, row)) for row in rows]
    return []

def get_auction_by_id(auction_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM auctions WHERE id = ?", (auction_id,))
    row = c.fetchone()
    conn.close()
    if row:
        columns = [desc[0] for desc in c.description]
        return dict(zip(columns, row))
    return None

def get_auction_by_message_id(message_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM auctions WHERE channel_message_id = ?", (message_id,))
    row = c.fetchone()
    conn.close()
    if row:
        columns = [desc[0] for desc in c.description]
        return dict(zip(columns, row))
    return None

def create_auction(**kwargs):
    kwargs['created_at'] = datetime.now().timestamp()
    conn = get_conn()
    c = conn.cursor()
    columns = ", ".join(kwargs.keys())
    placeholders = ", ".join("?" for _ in kwargs)
    c.execute(f"INSERT INTO auctions ({columns}) VALUES ({placeholders})", tuple(kwargs.values()))
    conn.commit()
    auction_id = c.lastrowid
    conn.close()
    return auction_id

def update_auction(auction_id: int, **kwargs):
    conn = get_conn()
    c = conn.cursor()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values())
    c.execute(f"UPDATE auctions SET {sets} WHERE id = ?", (*values, auction_id))
    conn.commit()
    conn.close()

def get_or_create_user(user_id: int, username: str = None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row:
        conn.close()
        columns = [desc[0] for desc in c.description]
        return dict(zip(columns, row))
    
    username = username or "NoUsername"
    c.execute("INSERT INTO users (user_id, username, started_chat) VALUES (?, ?, 0)", (user_id, username))
    conn.commit()
    conn.close()
    return get_or_create_user(user_id, username)

def update_user(user_id: int, **kwargs):
    conn = get_conn()
    c = conn.cursor()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values())
    c.execute(f"UPDATE users SET {sets} WHERE user_id = ?", (*values, user_id))
    conn.commit()
    conn.close()

def make_bid(auction_id: int, user_id: int, amount: int):
    conn = get_conn()
    c = conn.cursor()
    timestamp = datetime.now().timestamp()
    c.execute(
        "INSERT INTO bids (auction_id, user_id, amount, timestamp) VALUES (?, ?, ?, ?)",
        (auction_id, user_id, amount, timestamp)
    )
    bid_id = c.lastrowid
    
    c.execute(
        """UPDATE auctions 
           SET current_price = ?, last_bid_time = ?, bids_count = bids_count + 1 
           WHERE id = ?""",
        (amount, timestamp, auction_id)
    )
    conn.commit()
    conn.close()
    return bid_id

def get_bid_by_id(bid_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM bids WHERE id = ?", (bid_id,))
    row = c.fetchone()
    conn.close()
    if row:
        columns = [desc[0] for desc in c.description]
        return dict(zip(columns, row))
    return None

def get_bids_for_auction(auction_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT b.id, b.auction_id, b.user_id, b.amount, b.timestamp, b.canceled, u.username
        FROM bids b
        LEFT JOIN users u ON b.user_id = u.user_id
        WHERE b.auction_id = ?
        ORDER BY b.timestamp ASC
    """, (auction_id,))
    rows = c.fetchall()
    conn.close()
    if rows:
        columns = [desc[0] for desc in c.description]
        return [dict(zip(columns, row)) for row in rows]
    return []

def cancel_bid(bid_id: int, auction_id: int):
    conn = get_conn()
    c = conn.cursor()
    
    c.execute("UPDATE bids SET canceled = 1 WHERE id = ?", (bid_id,))
    
    c.execute(
        """SELECT amount FROM bids 
           WHERE auction_id = ? AND canceled = 0 AND id < ? 
           ORDER BY id DESC LIMIT 1""",
        (auction_id, bid_id)
    )
    prev = c.fetchone()
    
    if prev:
        new_price = prev[0]
    else:
        c.execute("SELECT start_price FROM auctions WHERE id = ?", (auction_id,))
        result = c.fetchone()
        new_price = result[0] if result else 0
    
    c.execute(
        "UPDATE auctions SET current_price = ?, bids_count = bids_count - 1 WHERE id = ?",
        (new_price, auction_id)
    )
    
    conn.commit()
    conn.close()

def get_user_last_bid(auction_id: int, user_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """SELECT * FROM bids 
           WHERE auction_id = ? AND user_id = ? AND canceled = 0 
           ORDER BY timestamp DESC LIMIT 1""",
        (auction_id, user_id)
    )
    row = c.fetchone()
    conn.close()
    if row:
        columns = [desc[0] for desc in c.description]
        return dict(zip(columns, row))
    return None