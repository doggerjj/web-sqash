import polars as pl
from datetime import datetime
from typing import Optional, Tuple
from erendil.trading.position import PositionManager
from erendil.models.data_models import MarketSignal
from erendil.indicators.buy_sell import BuySellIndicator
from erendil.indicators.trailing_stop import TrailingStoploss


class EnhancedMarketAnalyzer:
    def __init__(self):
        self.stoploss = TrailingStoploss()
        self.indicator = BuySellIndicator()
        
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
        ts_array, current_ts, prev_ts = self.stoploss.process_data(df)
        current_price, latest_timestamp = self._get_latest_values(df)
        
        signal = None
        
        # Check for signals using previous candle's trailing stop
        if current_price < prev_ts:  # Using previous candle's trailing stop
            signal = MarketSignal(
                action="SELL",
                price=current_price,
                timestamp=latest_timestamp,
                reason="Trailing stoploss hit"
            )
            return signal, current_ts

        elif self.indicator.check_buy_signal(hist_buy):
            return MarketSignal(
                action="BUY",
                price=current_price,
                timestamp=latest_timestamp,
                reason="Buy signal detected"
            ), current_ts
            
        elif self.indicator.check_sell_signal(hist_sell):
            return MarketSignal(
                action="SELL",
                price=current_price,
                timestamp=latest_timestamp,
                reason="Sell signal detected"
            ), current_ts
            
        return signal, current_ts