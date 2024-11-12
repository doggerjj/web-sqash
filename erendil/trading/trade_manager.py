import logging
import polars as pl
from typing import Optional
from datetime import datetime
from erendil.models.data_models import MarketSignal
from erendil.trading.position import PositionManager
from erendil.trading.analyzer import EnhancedMarketAnalyzer


logger = logging.getLogger(__name__)


class TradeManager:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.analyzer = EnhancedMarketAnalyzer()
        self.position_manager = PositionManager()
        
    def handle_signal(self, signal: Optional[MarketSignal]) -> None:
        """Process trading signals and manage positions"""
        if signal is None:
            return
            
        if signal.action == "BUY" and self.position_manager.position == 0:
            self.position_manager.position = 1
            self.position_manager.entry_price = signal.price
            logger.info(f"Opening position at {signal.price}")
            # Implement order placement logic here
            
        elif signal.action == "SELL" and self.position_manager.position > 0:
            if signal.reason == "Trailing stoploss hit":
                # Close entire position for stoploss
                self.position_manager.reset()
                logger.info(f"Closing position at {signal.price} due to stoploss")
            else:
                # Regular sell signal - close half position
                self.position_manager.position = 0
                logger.info(f"Closing position at {signal.price}")
            # Implement order placement logic here

    def process_data(self, df: pl.DataFrame) -> None:
        """Main processing function"""
        signal, _ = self.analyzer.calculate_signals(df)
        self.handle_signal(signal)