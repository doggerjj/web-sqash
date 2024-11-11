import asyncio
import logging
import polars as pl
from erendil.core.config import settings
from erendil.exchange.binance import BinanceExchange
from erendil.trading.analyzer import EnhancedMarketAnalyzer


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_callback(df: pl.DataFrame):
    """Example callback for processing kline data"""
    logger.info(f"Processing {len(df)} klines")
    analyzer = EnhancedMarketAnalyzer(settings.default_symbol)
    signal, stoploss = analyzer.calculate_signals(df)
    
    if signal:
        print(
            f"Signal: {signal.action} at {signal.timestamp}, "
            f"Price: {signal.price:.2f}, Reason: {signal.reason}"
        )
        if signal.action == "SELL_HALF":
            print(f"Trailing stoploss set at: {stoploss:.2f}")

async def main():
    # Create exchange instance
    exchange = BinanceExchange()
    
    try:
        # Add symbol streams
        asyncio.create_task(exchange.add_symbol_stream(
            symbol="btcusdt",
            interval="1m",
            callback=example_callback,
            limit=5000  # Optional, defaults to 1000
        ))
        
        # Keep the program running
        while True:
            await asyncio.sleep(1)
    
    except KeyboardInterrupt:
        # Clean shutdown
        await exchange.stop_all()

if __name__ == "__main__":
    asyncio.run(main())