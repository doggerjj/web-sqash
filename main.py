import asyncio
import logging
from erendil.exchange.binance import Erendil
from erendil.trading.trade_manager import TradeManager
from erendil.trading.analyzer import EnhancedMarketAnalyzer


logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
    # format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
        
        
async def main():
    interval = "1m"
    symbol = "ADAUSDT"
    trade_manager = TradeManager(
        max_buys = 3, fee_percent = 0.1, capital_per_trade = 100,
        log_file=f"{symbol}_{interval}_log_file.json", analyzer = EnhancedMarketAnalyzer()
    )  
    trader = Erendil(
        limit = 5000, interval = interval, symbol = symbol,
        onclose_callback = trade_manager.handle_candle_close,
        onmessage_callback = trade_manager.handle_price_update
    )
    try:
        await trader.run()
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        trade_manager.cleanup()
        await trader.stop()

if __name__ == "__main__":
    asyncio.run(main())