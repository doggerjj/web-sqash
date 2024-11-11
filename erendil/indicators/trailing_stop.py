import numpy as np
import polars as pl
from typing import Optional, Tuple
from erendil.indicators.base import BaseIndicator
from erendil.models.data_models import StoplossParams


class TrailingStoploss(BaseIndicator):
    def __init__(self, params: Optional[StoplossParams] = None):
        self.params = params or StoplossParams()
        self.prev_stoploss = None
    
    def calculate_atr(self, df: pl.DataFrame) -> np.ndarray:
        """Calculate ATR"""
        high = df['high'].to_numpy()
        low = df['low'].to_numpy()
        close = np.roll(df['close'].to_numpy(), 1)
        close[0] = df['close'][0]
        
        tr = np.maximum(
            high - low,
            np.maximum(
                np.abs(high - close),
                np.abs(low - close)
            )
        )
        
        # Calculate ATR using Wilder's smoothing
        atr = np.zeros_like(tr)
        atr[0] = tr[0]
        for i in range(1, len(tr)):
            atr[i] = ((atr[i-1] * (self.params.atr_period - 1)) + tr[i]) / self.params.atr_period
        
        return atr
    
    def process_data(self, df: pl.DataFrame) -> Tuple[np.ndarray, float]:
        """
        Process data and return trailing stoploss array and current value
        Returns:
            Tuple of (stoploss array, current stoploss value)
        """
        if len(df) < max(self.params.atr_period, self.params.hhv_period):
            return np.array([]), 0.0
        
        # Calculate ATR
        atr = self.calculate_atr(df)
        
        # Calculate offset (high - multiplier * ATR)
        high = df['high'].to_numpy()
        offset = high - (self.params.multiplier * atr)
        
        # Calculate highest values over HHV period
        highest = np.zeros_like(offset)
        for i in range(len(offset)):
            start_idx = max(0, i - self.params.hhv_period + 1)
            highest[i] = np.max(offset[start_idx:i+1])
        
        # Calculate trailing stoploss
        close = df['close'].to_numpy()
        ts = np.zeros_like(close)
        ts[0] = close[0]
        
        for i in range(1, len(close)):
            if close[i] > highest[i] and close[i] > close[i-1]:
                ts[i] = highest[i]
            else:
                ts[i] = ts[i-1]
        
        return ts, ts[-1]