from typing import Dict
from dataclasses import dataclass
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from erendil.models.enums import MAType, SmoothingType


@dataclass
class StoplossParams:
    atr_period: int = 5
    hhv_period: int = 10
    multiplier: float = 2.5

@dataclass
class IndicatorParams:
    fast_length: int = 12
    slow_length: int = 26
    atr_avg_length: int = 12
    signal_length: int = 9
    oscillator_ma: MAType = MAType.EMA
    signal_ma: MAType = MAType.EMA
    smoothing_length: int = 10
    smoothing: SmoothingType = SmoothingType.RMA


class MarketSignal(BaseModel):
    price:     float
    action:    str
    reason:    str
    timestamp: datetime

class KlineData(BaseModel):    
    volume:                 float
    trades:                 int
    open_time:              datetime
    low_price:              float = Field(alias="low")
    open_price:             float = Field(alias="open")
    high_price:             float = Field(alias="high")
    close_time:             datetime
    close_price:            float = Field(alias="close")
    quote_volume:           float
    taker_buy_volume:       float
    taker_buy_quote_volume: float
    
    class Config:
        populate_by_name = True
        
class WebsocketKline(BaseModel):
    symbol:     str = Field(alias="s")
    event_type: str = Field(alias="e")
    kline:      Dict = Field(alias="k")
    event_time: datetime = Field(alias="E")

    @property
    def to_kline_data(self) -> KlineData:
        k = self.kline
        return KlineData(
            open_time=datetime.fromtimestamp(k['t'] / 1000, tz=timezone.utc),
            open=float(k['o']),
            high=float(k['h']),
            low=float(k['l']),
            close=float(k['c']),
            volume=float(k['v']),
            close_time=datetime.fromtimestamp(k['T'] / 1000, tz=timezone.utc),
            quote_volume=float(k['q']),
            trades=int(k['n']),
            taker_buy_volume=float(k['V']),
            taker_buy_quote_volume=float(k['Q'])
        )