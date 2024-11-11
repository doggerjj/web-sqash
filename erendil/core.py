import json
import httpx
import asyncio
import logging
import websockets
import polars as pl
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import List, Dict, Callable, Optional, Any
from erendil.pydantic_models import MarketSignal, WebsocketKline, KlineData


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MarketAnalyzer:
    """Example class for market analysis and order placement"""
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.last_signal: Optional[str] = None
    
    def analyze_market(self, df: pl.DataFrame) -> Optional[MarketSignal]:
        """
        Sample analysis function using simple moving averages
        """
        if len(df) < 50:
            return None
            
        # Calculate indicators
        df = df.with_columns([
            pl.col("close").rolling_mean(20).alias("sma_20"),
            pl.col("close").rolling_mean(50).alias("sma_50"),
            pl.col("volume").rolling_mean(20).alias("volume_ma")
        ])
        
        latest = df.tail(1)
        
        # Generate signals based on SMA crossover
        if latest["sma_20"][0] > latest["sma_50"][0] and self.last_signal != "BUY":
            self.last_signal = "BUY"
            return MarketSignal(
                action="BUY",
                price=latest["close"][0],
                timestamp=latest["close_time"][0],
                reason="SMA20 crossed above SMA50"
            )
        elif latest["sma_20"][0] < latest["sma_50"][0] and self.last_signal != "SELL":
            self.last_signal = "SELL"
            return MarketSignal(
                action="SELL",
                price=latest["close"][0],
                timestamp=latest["close_time"][0],
                reason="SMA20 crossed below SMA50"
            )
        
        return None
    

class BinanceKlineManager:
    def __init__(self, 
                 symbol: str, 
                 interval: str, 
                 callback: Callable[[pl.DataFrame], None],
                 limit: int = 1000):
        self.symbol = symbol.lower()
        self.interval = interval
        self.limit = limit
        self.callback = callback
        self.base_rest_url = "https://api.binance.com/api/v3"
        self.ws_url = f"wss://stream.binance.com:9443/ws/{self.symbol}@kline_{self.interval}"
        self.historical_data: Optional[pl.DataFrame] = None
        
    def kline_to_polars(self, kline: KlineData) -> pl.DataFrame:
        """Convert KlineData to Polars DataFrame"""
        return pl.DataFrame([{
            "open_time": kline.open_time,
            "open": kline.open_price,
            "high": kline.high_price,
            "low": kline.low_price,
            "close": kline.close_price,
            "volume": kline.volume,
            "close_time": kline.close_time,
            "quote_volume": kline.quote_volume,
            "trades": kline.trades,
            "taker_buy_volume": kline.taker_buy_volume,
            "taker_buy_quote_volume": kline.taker_buy_quote_volume
        }])
    
    async def fetch_historical_data(self) -> None:
        """Fetch historical kline data using REST API"""
        async with httpx.AsyncClient() as client:
            url = f"{self.base_rest_url}/klines"
            params = {
                "limit": self.limit,
                "interval": self.interval,
                "symbol": self.symbol.upper(),
            }
            
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                # Convert raw data to KlineData objects
                klines = [
                    KlineData(
                        open_time=datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc),
                        open=float(k[1]),
                        high=float(k[2]),
                        low=float(k[3]),
                        close=float(k[4]),
                        volume=float(k[5]),
                        close_time=datetime.fromtimestamp(k[6] / 1000, tz=timezone.utc),
                        quote_volume=float(k[7]),
                        trades=int(k[8]),
                        taker_buy_volume=float(k[9]),
                        taker_buy_quote_volume=float(k[10])
                    )
                    for k in data
                ]
                
                # Convert to Polars DataFrame
                dfs = [self.kline_to_polars(kline) for kline in klines]
                self.historical_data = pl.concat(dfs)
                
                logger.info(f"Fetched {len(self.historical_data)} historical klines")
                
                # Initial callback with historical data
                await self.process_data()
                
            except Exception as e:
                logger.error(f"Error fetching historical data: {e}")
                raise
    
    async def process_data(self):
        """Process the current state of data using the callback"""
        if self.historical_data is not None:
            try:
                await asyncio.create_task(self.callback(self.historical_data))
            except Exception as e:
                logger.error(f"Error in callback processing: {e}")
    
    async def start_websocket_stream(self):
        """Start websocket connection and process real-time kline data"""
        while True:
            try:
                async with websockets.connect(self.ws_url) as websocket:
                    logger.info("WebSocket connection established")
                    
                    while True:
                        message = await websocket.recv()
                        ws_data = WebsocketKline.model_validate_json(message)
                        
                        # Only process completed klines
                        if ws_data.kline.get('x', False):
                            kline_data = ws_data.to_kline_data
                            new_row = self.kline_to_polars(kline_data)
                            
                            # Append to historical data
                            if self.historical_data is not None:
                                self.historical_data = pl.concat([
                                    self.historical_data,
                                    new_row
                                ])
                                
                                logger.info(
                                    f"New kline added - Time: {kline_data.close_time}, "
                                    f"Close: {kline_data.close_price:.2f}"
                                )
                                
                                # Process updated data
                                await self.process_data()
                            
            except websockets.ConnectionClosed:
                logger.warning("WebSocket connection closed, attempting to reconnect...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await asyncio.sleep(5)