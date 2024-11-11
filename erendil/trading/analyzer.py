import polars as pl
from datetime import datetime
from typing import Optional, Tuple
from erendil.trading.position import PositionManager
from erendil.models.data_models import MarketSignal
from erendil.indicators.buy_sell import BuySellIndicator
from erendil.indicators.trailing_stop import TrailingStoploss


class EnhancedMarketAnalyzer:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.stoploss = TrailingStoploss()
        self.indicator = BuySellIndicator()
        self.last_signal: Optional[str] = None
        self.position_manager = PositionManager()
        
    def _get_latest_values(self, df: pl.DataFrame) -> Tuple[float, datetime]:
        """Get latest price and timestamp from DataFrame"""
        latest_row = df.tail(1)
        return (
            latest_row['close'][0],
            latest_row['close_time'][0]
        )
        
    def calculate_signals(self, df: pl.DataFrame) -> Tuple[Optional[MarketSignal], Optional[float]]:
        if len(df) < max(self.indicator.params.slow_length, self.stoploss.params.hhv_period) + 2:
            return None, None
        
        hist_buy, hist_sell = self.indicator.process_data(df)
        ts_array, current_ts = self.stoploss.process_data(df)
        current_price, latest_timestamp = self._get_latest_values(df)
        
        signal = None
        
        if self.position_manager.position == 0.5:
            if current_price < ts_array[-2]:
                signal = MarketSignal(
                    action="SELL_REMAINING",
                    price=current_price,
                    timestamp=latest_timestamp,
                    reason="Trailing stoploss hit"
                )
                self.position_manager.reset()
                return signal, current_ts
        
        # Check for initial sell signal
        if (self.indicator.check_sell_signal(hist_sell) and 
            self.position_manager.position == 1):
            self.position_manager.position = 0.5
            self.position_manager.trailing_stoploss = current_ts
            signal = MarketSignal(
                action="SELL_HALF",
                price=current_price,
                timestamp=latest_timestamp,
                reason="Sell signal detected"
            )
        
        # Check for buy signal
        elif (self.indicator.check_buy_signal(hist_buy) and 
              self.position_manager.position == 0):
            self.position_manager.position = 1
            signal = MarketSignal(
                action="BUY",
                price=current_price,
                timestamp=latest_timestamp,
                reason="Buy signal detected"
            )
        
        return signal, current_ts