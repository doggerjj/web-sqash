import hashlib
import logging, aiosqlite
from datetime import datetime
from typing import Optional, Dict, List


logger = logging.getLogger(__name__)


class TradeDatabase:
    def __init__(self, db_path: str = "trades.db"):
        self.db_path = db_path

    async def initialize(self):
        """Initialize the database and create necessary tables"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    price REAL NOT NULL,
                    fee REAL NOT NULL,
                    pnl REAL,
                    signal_reason TEXT NOT NULL,
                    position_size REAL NOT NULL,
                    total_invested REAL NOT NULL,
                    entry_price REAL,
                    remaining_position REAL NOT NULL,
                    total_pnl REAL,
                    timestamp TEXT NOT NULL,
                    trade_hash TEXT UNIQUE,
                    interval TEXT NOT NULL
                )
            ''')
            await db.commit()

    def _generate_trade_hash(self, trade: Dict) -> str:
        """Generate a unique hash for a trade based on key attributes."""
        trade_string = f"{trade['timestamp']}_{trade['action']}_{trade['price']}_{trade['position_size']}"
        hash_object = hashlib.sha256()
        hash_object.update(trade_string.encode())
        return hash_object.hexdigest()

    async def save_trade(self, trade: Dict, symbol: str, interval: str) -> bool:
        """Save a trade to the database with duplicate prevention"""
        trade_hash = self._generate_trade_hash(trade)
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Check for duplicate
                cursor = await db.execute(
                    'SELECT COUNT(*) FROM trades WHERE trade_hash = ?', 
                    (trade_hash,)
                )
                count = await cursor.fetchone()
                
                if count[0] > 0:
                    logger.warning(f"Duplicate trade detected and skipped: {trade_hash}")
                    return False

                # Insert new trade
                await db.execute('''
                    INSERT INTO trades (
                        symbol, action, price, fee, pnl, signal_reason,
                        position_size, total_invested, entry_price,
                        remaining_position, total_pnl, timestamp,
                        trade_hash, interval
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol, trade['action'], trade['price'], trade['fee'],
                    trade['pnl'], trade['signal_reason'], trade['position_size'],
                    trade['total_invested'], trade['entry_price'],
                    trade['remaining_position'], trade['total_pnl'],
                    trade['timestamp'], trade_hash, interval
                ))
                await db.commit()
                return True

        except Exception as e:
            logger.error(f"Error saving trade to database: {e}")
            return False

    async def get_trades(self, symbol: str, interval: str) -> List[Dict]:
        """Retrieve trades for a symbol and interval"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM trades WHERE symbol = ? AND interval = ? ORDER BY timestamp',
                (symbol, interval)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]