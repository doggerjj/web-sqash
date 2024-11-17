import numpy as np
import polars as pl
from typing import Optional, Tuple
from erendil.indicators.base import BaseIndicator
from erendil.models.data_models import IndicatorParams, MAType, SmoothingType


class BuySellIndicator(BaseIndicator):
    def __init__(self, params: Optional[IndicatorParams] = None):
        self.params = params or IndicatorParams()
        
    def calculate_rma(self, data: np.ndarray, length: int) -> np.ndarray:
        """Calculate RMA (Running Moving Average / Wilders Smoothing)"""
        alpha = 1.0 / length
        result = np.zeros_like(data)
        result[0] = data[0]  # Initialize first value
        
        for i in range(1, len(data)):
            result[i] = alpha * data[i] + (1 - alpha) * result[i-1]
        
        return result
    
    def calculate_wma(self, data: np.ndarray, length: int) -> np.ndarray:
        """Calculate WMA (Weighted Moving Average)"""
        weights = np.arange(1, length + 1)
        weights = weights / weights.sum()
        return np.convolve(data, weights[::-1], mode='valid')

    def calculate_ema(self, data: np.ndarray, length: int) -> np.ndarray:
        """Calculate EMA (Exponential Moving Average)"""
        alpha = 2.0 / (length + 1)
        result = np.zeros_like(data)
        result[0] = data[0]
        
        for i in range(1, len(data)):
            result[i] = alpha * data[i] + (1 - alpha) * result[i-1]
        
        return result
    
    def calculate_sma(self, data: np.ndarray, length: int) -> np.ndarray:
        """Calculate SMA (Simple Moving Average)"""
        return np.convolve(data, np.ones(length)/length, mode='valid')
    
    def ma_function(self, data: np.ndarray, length: int, smoothing_type: SmoothingType) -> np.ndarray:
        """Implement the ma_function from PineScript"""
        if smoothing_type == SmoothingType.RMA:
            return self.calculate_rma(data, length)
        elif smoothing_type == SmoothingType.SMA:
            return self.calculate_sma(data, length)
        elif smoothing_type == SmoothingType.EMA:
            return self.calculate_ema(data, length)
        else:  # WMA
            return self.calculate_wma(data, length)
    
    def calculate_tr(self, df: pl.DataFrame) -> np.ndarray:
        """Calculate True Range"""
        high = df['high'].to_numpy()
        low = df['low'].to_numpy()
        prev_close = np.roll(df['close'].to_numpy(), 1)
        prev_close[0] = df['close'][0]
        
        tr = np.maximum(
            high - low,
            np.maximum(
                np.abs(high - prev_close),
                np.abs(low - prev_close)
            )
        )
        return tr
    
    def process_data(self, df: pl.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        if len(df) < self.params.slow_length:
            return np.array([]), np.array([])

        close = df['close'].to_numpy()
        
        # Calculate MACD components
        if self.params.oscillator_ma == MAType.SMA:
            fast_ma = self.calculate_sma(close, self.params.fast_length)
            slow_ma = self.calculate_sma(close, self.params.slow_length)
        else:  # EMA
            fast_ma = self.calculate_ema(close, self.params.fast_length)
            slow_ma = self.calculate_ema(close, self.params.slow_length)
        
        macd = fast_ma - slow_ma
        
        # Calculate signal line
        if self.params.signal_ma == MAType.SMA:
            signal = self.calculate_sma(macd, self.params.signal_length)
        else:  # EMA
            signal = self.calculate_ema(macd, self.params.signal_length)
        
        # Calculate TR
        tr = self.calculate_tr(df)
        
        # Buy signal calculation
        atrn_buy = self.ma_function(tr * (-1.25), self.params.smoothing_length, self.params.smoothing)
        atr_avg_buy = self.calculate_ema(atrn_buy, self.params.atr_avg_length)
        hist_buy = signal - (atr_avg_buy - signal)
        
        # Sell signal calculation
        atrn_sell = self.ma_function(tr * 1.25, self.params.smoothing_length, self.params.smoothing)
        atr_avg_sell = self.calculate_ema(atrn_sell, self.params.atr_avg_length)
        hist_sell = signal - (atr_avg_sell - signal)
        
        return hist_buy, hist_sell
    
    def check_buy_signal(self, hist: np.ndarray) -> bool:
        """Check for buy signal pattern"""
        if len(hist) < 3:
            return False
        return (hist[-1] > hist[-2] and  # Current bar growing
                hist[-2] < hist[-3] and  # Previous bar falling
                hist[-1] <= 0)  # Below zero

    def check_sell_signal(self, hist: np.ndarray) -> bool:
        """Check for sell signal pattern"""
        if len(hist) < 3:
            return False
        return (hist[-1] < hist[-2] and  # Current bar falling
                hist[-2] > hist[-3] and  # Previous bar growing
                hist[-1] >= 0)  # Above zero