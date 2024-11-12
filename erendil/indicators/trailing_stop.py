import numpy as np
import polars as pl
from typing import Optional, Tuple
from erendil.indicators.base import BaseIndicator
from erendil.models.data_models import StoplossParams


class TrailingStoploss(BaseIndicator):
    def __init__(self, params: Optional[StoplossParams] = None):
        self.params = params or StoplossParams()
    
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
    
    def process_data(self, df: pl.DataFrame) -> Tuple[np.ndarray, float, float]:
        """
        Process data and return trailing stoploss array and values
        Returns:
            Tuple of (stoploss array, current ts, previous ts)
        """
        if len(df) < max(self.params.atr_period, self.params.hhv_period):
            return np.array([]), 0.0, 0.0
            
        close = df['close'].to_numpy()
        high = df['high'].to_numpy()
        atr = self.calculate_atr(df)
        
        # Calculate offset (high - multiplier * ATR)
        offset = high - (self.params.multiplier * atr)
        
        # Calculate highest values over HHV period
        highest = np.zeros_like(offset)
        for i in range(len(offset)):
            start_idx = max(0, i - self.params.hhv_period + 1)
            highest[i] = np.max(offset[start_idx:i+1])
        
        # Initialize prev array
        prev = np.copy(highest)
        
        # Calculate trailing stoploss exactly as in PineScript
        ts = np.zeros_like(close)
        
        for i in range(len(close)):
            if i < 16:  # cum_1 < 16 condition
                ts[i] = close[i]
            else:
                condition = (close[i] > highest[i] and 
                           close[i] > close[i-1])
                ts[i] = highest[i] if condition else prev[i]
                
            prev[i+1:] = ts[i]  # Update prev for next iterations
            
        return ts, ts[-1], ts[-2] if len(ts) > 1 else ts[-1]