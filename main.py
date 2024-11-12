import asyncio
import logging
import polars as pl
from erendil.core.config import settings
from datetime import datetime, timedelta, timezone
from erendil.exchange.binance import BinanceExchange
from erendil.trading.trade_manager import TradeManager
from erendil.trading.analyzer import EnhancedMarketAnalyzer


logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
    # format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
        
        
async def main():
    limit = 5000
    interval = "1m"
    symbol = "BTCUSDT"
    exchange = BinanceExchange()
    analyzer = EnhancedMarketAnalyzer()
    
    def convert_to_ist(utc_time: datetime) -> datetime:
        """Convert UTC datetime to IST datetime"""
        ist = timezone(timedelta(hours=5, minutes=30))
        return utc_time.astimezone(ist)
    
    def handle_candle_close(df):
        """Callback for completed candles"""
        signal, _ = analyzer.calculate_signals(df)
        if signal and (signal.reason != "Trailing stoploss hit"):
            logger.info(f"Signal generated: {convert_to_ist(signal.timestamp)} | {signal.action} | {signal.price} | {signal.reason}")
            # Here you would implement order execution logic
                
    def handle_price_update(df):
        """Callback for real-time price updates"""
        signal, _ = analyzer.calculate_signals(df)
        if signal and (signal.reason != "Trailing stoploss hit"):
            logger.info(f"Signal generated: {convert_to_ist(signal.timestamp)} | {signal.action} | {signal.price} | {signal.reason}")
            # Here you would implement order execution logic
        
            
    try:
        logger.info(f"Starting trading bot for {symbol}")
        await exchange.add_symbol_stream(
            limit=limit,
            symbol=symbol,
            interval=interval,
            onclose_callback=handle_candle_close,
            onmessage_callback=handle_price_update
        )
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await exchange.stop_all()


if __name__ == "__main__":
    asyncio.run(main())