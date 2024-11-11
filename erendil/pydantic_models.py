from typing import Dict
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict


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