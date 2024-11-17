import numpy as np
import polars as pl
from typing import Optional, Tuple
from erendil.indicators.base import BaseIndicator
from erendil.models.data_models import StoplossParams


class TrailingStoploss(BaseIndicator):
    def __init__(self, params: Optional[StoplossParams] = None):
        self.params = params or StoplossParams()
    
    def calculate_atr(self, df: pl.DataFrame) -> np.ndarray:
        """Calculate ATR using Wilder's smoothing - needs fixing"""
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
        
        # Use Wilder's smoothing
        atr = np.zeros_like(tr)
        atr[0] = tr[0]
        for i in range(1, len(tr)):
            atr[i] = (atr[i-1] * (self.params.atr_period - 1) + tr[i]) / self.params.atr_period
            
        return atr
        
    def process_data(self, df: pl.DataFrame) -> Tuple[np.ndarray, float, float]:
        if len(df) < max(self.params.atr_period, self.params.hhv_period):
            return np.array([]), 0.0, 0.0
            
        close = df['close'].to_numpy()
        high = df['high'].to_numpy()
        atr = self.calculate_atr(df)
        
        # Calculate offset
        offset = high - (self.params.multiplier * atr)
        
        # Calculate rolling highest properly
        highest = np.zeros_like(offset)
        prev = np.zeros_like(offset)
        
        for i in range(len(offset)):
            start_idx = max(0, i - self.params.hhv_period + 1)
            highest[i] = np.max(offset[start_idx:i+1])
            prev[i] = highest[i]
        
        ts = np.zeros_like(close)
        
        for i in range(len(close)):
            if i < 16:
                ts[i] = close[i]
            else:
                condition = close[i] > highest[i] and close[i] > close[i-1]
                ts[i] = highest[i] if condition else prev[i]
            if i + 1 < len(prev):
                prev[i+1] = ts[i]
        
        return ts, ts[-1], ts[-2] if len(ts) > 1 else ts[-1]