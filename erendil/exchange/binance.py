import json
import httpx
import logging
import asyncio
import websockets
import polars as pl
from datetime import datetime, timezone
from erendil.core.config import settings
from websockets.exceptions import ConnectionClosed
from typing import Optional, Callable, Dict, Any, List
from erendil.models.exceptions import BinanceAPIException
from erendil.models.data_models import KlineData, WebsocketKline
from erendil.core.constants import BINANCE_BASE_URL, BINANCE_WS_URL


logger = logging.getLogger(__name__)


class BinanceKlineManager:
    def __init__(
        self,
        symbol: str,
        interval: str,
        callback: Callable[[pl.DataFrame], None],
        limit: int = 1000,
        retry_delay: int = 5,
        max_retries: int = 3,
        semaphore_limit: int = 10
    ):
        """
        Initialize the Binance Kline Manager.
        
        Args:
            symbol: Trading pair symbol (e.g., 'btcusdt')
            interval: Kline interval (e.g., '1m', '5m', '1h')
            callback: Function to process the data
            limit: Maximum number of historical klines to fetch
            retry_delay: Delay between retries in seconds
            max_retries: Maximum number of retry attempts
            semaphore_limit: Maximum number of concurrent requests
        """
        self.symbol = symbol.lower()
        self.interval = interval
        self.limit = limit
        self.callback = callback
        self.retry_delay = retry_delay
        self.max_retries = max_retries
        self.request_semaphore = asyncio.Semaphore(semaphore_limit)
        
        self.historical_data: Optional[pl.DataFrame] = None
        self.is_running = False
        
        # API endpoints
        self.base_rest_url = f"{BINANCE_BASE_URL}/api/v3"
        self.ws_url = f"{BINANCE_WS_URL}/{self.symbol}@kline_{self.interval}"
        
        # Authentication headers if API keys are provided
        self.headers = {}
        if settings.binance_api_key:
            self.headers["X-MBX-APIKEY"] = settings.binance_api_key
            
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
    
    async def _make_request(self, method: str, endpoint: str, params: Dict[str, Any] = None) -> Any:
        """Make HTTP request to Binance API with retry logic"""
        url = f"{self.base_rest_url}/{endpoint}"
        
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        params=params,
                        headers=self.headers,
                        timeout=30.0
                    )
                    response.raise_for_status()
                    return response.json()
                    
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # Rate limit exceeded
                    retry_after = int(e.response.headers.get('Retry-After', self.retry_delay))
                    logger.warning(f"Rate limit exceeded. Waiting {retry_after} seconds...")
                    await asyncio.sleep(retry_after)
                    continue
                    
                raise BinanceAPIException(f"HTTP error occurred: {e.response.text}")
                
            except httpx.RequestError as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
                raise BinanceAPIException(f"Request failed: {str(e)}")
    
    async def fetch_historical_data(self) -> None:
        """Fetch historical kline data using parallel requests"""
        try:
            # Calculate number of requests needed and time ranges
            requests_needed = (self.limit + 999) // 1000  # Ceiling division
            batch_size = 1000
            
            end_time = int(datetime.now(timezone.utc).timestamp() * 1000)
            interval_ms = self._get_interval_ms(self.interval)
            batch_ms = interval_ms * batch_size
            
            # Create time ranges for each request
            time_ranges = []
            for i in range(requests_needed):
                start = end_time - batch_ms
                time_ranges.append((start, end_time))
                end_time = start - 1
            
            # Create tasks for parallel execution
            tasks = [
                self._fetch_klines_batch(start_time, end_time)
                for start_time, end_time in time_ranges
            ]
            
            # Execute all requests in parallel
            batches = await asyncio.gather(*tasks)
            
            # Combine and sort all klines
            all_klines = []
            for batch in batches:
                all_klines.extend(batch)
            
            # Convert to Polars DataFrame
            if all_klines:
                dfs = [self.kline_to_polars(kline) for kline in all_klines]
                self.historical_data = pl.concat(dfs)
                
                # Sort by open_time and remove duplicates
                self.historical_data = (
                    self.historical_data
                    .sort("open_time")
                    .unique(subset=["open_time"])
                    .tail(self.limit)
                )
                
                logger.info(f"Fetched {len(self.historical_data)} historical klines")
                await self.process_data()
            else:
                logger.warning("No historical data retrieved")
            
        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            raise

    def _get_interval_ms(self, interval: str) -> int:
        """Convert interval string to milliseconds"""
        multipliers = {
            's': 1000,
            'm': 60 * 1000,
            'h': 60 * 60 * 1000,
            'd': 24 * 60 * 60 * 1000,
            'w': 7 * 24 * 60 * 60 * 1000,
            'M': 30 * 24 * 60 * 60 * 1000
        }
        
        unit = interval[-1]
        number = int(interval[:-1])
        
        if unit not in multipliers:
            raise ValueError(f"Invalid interval: {interval}")
        
        return number * multipliers[unit]

    async def _fetch_klines_batch(
        self, 
        start_time: int, 
        end_time: int
    ) -> List[KlineData]:
        """Fetch a single batch of klines"""
        params = {
            "symbol": self.symbol.upper(),
            "interval": self.interval,
            "limit": 1000,
            "startTime": start_time,
            "endTime": end_time
        }
        async with self.request_semaphore:
            try:
                data = await self._make_request("GET", "klines", params)
                
                return [
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
            except Exception as e:
                logger.error(f"Error fetching batch {start_time}-{end_time}: {e}")
                return []
    
    async def process_data(self) -> None:
        """Process the current state of data using the callback"""
        if self.historical_data is not None:
            try:
                await asyncio.create_task(self.callback(self.historical_data))
            except Exception as e:
                logger.error(f"Error in callback processing: {e}")
    
    async def process_realtime_price(self, price: float) -> None:
        """Process realtime price updates"""
        if self.historical_data is not None:
            df_copy = self.historical_data.clone()
            df_copy = df_copy.with_columns(pl.lit(price).alias("close").cast(pl.Float64))
            await self.process_data()
    
    async def _handle_websocket_message(self, message: str) -> None:
        """Handle incoming websocket messages"""
        try:
            ws_data = WebsocketKline.parse_raw(message)
            
            # Process realtime price for trailing stoploss
            current_price = float(ws_data.kline['c'])
            await self.process_realtime_price(current_price)
            
            # Process completed candles
            if ws_data.kline.get('x', False):
                kline_data = ws_data.to_kline_data
                new_row = self.kline_to_polars(kline_data)
                
                self.historical_data = pl.concat([
                    self.historical_data,
                    new_row
                ])
                
                logger.info(
                    f"New kline added - Time: {kline_data.close_time}, "
                    f"Close: {kline_data.close_price:.2f}"
                )
                
                await self.process_data()
                
        except Exception as e:
            logger.error(f"Error processing websocket message: {e}")
    
    async def _maintain_websocket(self) -> None:
        """Maintain the websocket connection with heartbeat"""
        while self.is_running:
            try:
                async with websockets.connect(self.ws_url) as websocket:
                    logger.info("WebSocket connection established")
                    
                    # Set up ping/pong
                    ping_task = asyncio.create_task(self._ping_websocket(websocket))
                    
                    try:
                        while self.is_running:
                            message = await websocket.recv()
                            await self._handle_websocket_message(message)
                    
                    except ConnectionClosed:
                        logger.warning("WebSocket connection closed")
                    
                    finally:
                        ping_task.cancel()
                        try:
                            await ping_task
                        except asyncio.CancelledError:
                            pass
            
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                if self.is_running:
                    await asyncio.sleep(self.retry_delay)
    
    async def _ping_websocket(self, websocket: websockets.WebSocketClientProtocol) -> None:
        """Send periodic pings to keep the connection alive"""
        while True:
            try:
                await asyncio.sleep(180)  # Ping every 3 minutes
                await websocket.ping()
            except Exception as e:
                logger.error(f"Error in ping: {e}")
                break
    
    async def start_websocket_stream(self) -> None:
        """Start the websocket stream"""
        self.is_running = True
        try:
            await self._maintain_websocket()
        finally:
            self.is_running = False
    
    async def stop(self) -> None:
        """Stop the websocket stream"""
        self.is_running = False
        
    

class BinanceExchange:
    """Main Binance exchange interface"""
    def __init__(self):
        self.kline_managers: Dict[str, BinanceKlineManager] = {}
    
    async def add_symbol_stream(
        self,
        symbol: str,
        interval: str,
        callback: Callable[[pl.DataFrame], None],
        limit: int = 1000,
    ) -> None:
        """Add a new symbol stream"""
        manager = BinanceKlineManager(
            limit=limit,
            symbol=symbol,
            interval=interval,
            callback=callback,
        )
        self.kline_managers[symbol] = manager
        
        await manager.fetch_historical_data()
        await manager.start_websocket_stream()
    
    async def remove_symbol_stream(self, symbol: str) -> None:
        """Remove a symbol stream"""
        if symbol in self.kline_managers:
            await self.kline_managers[symbol].stop()
            del self.kline_managers[symbol]
    
    async def stop_all(self) -> None:
        """Stop all symbol streams"""
        for manager in self.kline_managers.values():
            await manager.stop()
        self.kline_managers.clear()