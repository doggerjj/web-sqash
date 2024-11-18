import asyncio
import logging
from erendil.exchange.binance import Erendil
from erendil.trading.trade_manager import TradeManager


logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
    # format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
        
        
async def main():
    interval = "1m"
    symbol = "ATOMUSDT"
    trade_manager = TradeManager(
        symbol=symbol, interval=interval,
        fee_percent = 0.1, capital_per_trade = 100,
        max_buys = 3, log_file=f"{symbol}_{interval}_log_file.json",
        db_path=f"{symbol}_{interval}_trades.db"
    )  
    trader = Erendil(
        limit = 5000, interval = interval, symbol = symbol,
        onclose_callback = trade_manager.handle_candle_close,
        onmessage_callback = trade_manager.handle_price_update
    )
    
    await trade_manager.initialize()
    try:
        await trader.run()
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await trader.stop()

if __name__ == "__main__":
    asyncio.run(main())