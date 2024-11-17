import polars as pl
import logging, json
from datetime import datetime
from typing import Optional, Dict, List
from datetime import datetime, timedelta, timezone
from erendil.models.data_models import MarketSignal
from erendil.trading.position import PositionManager
from erendil.indicators.buy_sell import BuySellIndicator
from erendil.indicators.trailing_stop import TrailingStoploss


logger = logging.getLogger(__name__)
        

class TradeManager:
    def __init__(self, symbol: str, interval: str, capital_per_trade: float=100, fee_percent: float=0.1, max_buys: int=3, log_file: str = "trade_log.json"):
        self.pnl = 0
        self.buy_count = 0
        self.trade_log = []
        self.symbol = symbol
        self.total_invested = 0
        self.interval = interval
        self.max_buys = max_buys
        self.log_file = log_file
        self.fee_percent = fee_percent
        self.cached_trailing_stop = None
        self.stoploss = TrailingStoploss()
        self.indicator = BuySellIndicator()
        self.position_log = PositionManager()
        self.capital_per_trade = capital_per_trade
        
    def _convert_to_ist(self, utc_time: datetime) -> datetime:
        ist = timezone(timedelta(hours=5, minutes=30))
        return utc_time.astimezone(ist)
    
    def _save_trade_entry(self, trade_entry: Dict):
        """Save trade entry to log file using aiofiles"""
        try:
            json_data = {
                "symbol": self.symbol,
                "trades": [trade_entry],
                "interval": self.interval,
            }
            try:
                with open(self.log_file, 'r') as f:
                    content = f.read()
                    json_data = json.loads(content) if content else json_data
            except FileNotFoundError:
                pass
            json_data['trades'].append(trade_entry)
            with open(self.log_file, 'w') as f:
                f.write(json.dumps(json_data, indent=2, default=str))
            logger.debug(f"Trade entry saved successfully to {self.log_file}")
        except Exception as e:
            logger.error(f"Error saving trade log: {e}")
    
    def _create_trade_entry(self, signal: MarketSignal, action: str, position_size: float, 
        fee: float, pnl: Optional[float] = None) -> Dict:
        """Create a trade entry dictionary"""
        return {
            "fee": fee,
            "pnl": pnl,
            "action": action,
            "price": signal.price,
            "signal_reason": signal.reason,
            "position_size": position_size,
            "total_invested": self.total_invested,
            "entry_price": self.position_log.entry_price,
            "remaining_position": self.position_log.position,
            "total_pnl": self.pnl if pnl is not None else None,
            "timestamp": self._convert_to_ist(signal.timestamp).isoformat(),
        }
        
    def buy(self, signal: MarketSignal):
        
        # Check if max buys limit reached
        if self.buy_count >= self.max_buys:
            logger.info(f"Max buys ({self.max_buys}) reached, skipping buy signal at price {signal.price}")
            return
        
        # Calculate fee for buying
        fee = self.capital_per_trade * (self.fee_percent / 100)
        
        # For new position
        if self.position_log.position == 0:
            position = (self.capital_per_trade - fee) / signal.price
            self.position_log.entry_price = signal.price
            self.total_invested = self.capital_per_trade
            self.buy_count = 1
            logger.info(f"Opening new position: Price={signal.price}, Size={position:.6f}, Fee={fee:.2f}")
            
        # For DCA - only if new price is lower than entry price
        elif signal.price < self.position_log.entry_price:
            position = (self.capital_per_trade - fee) / signal.price
            # Update average entry price
            total_position = self.position_log.position + position
            total_cost = (self.position_log.position * self.position_log.entry_price) + (position * signal.price)
            old_entry = self.position_log.entry_price
            self.position_log.entry_price = total_cost / total_position
            self.total_invested += self.capital_per_trade
            self.buy_count += 1
            logger.info(f"DCA buy #{self.buy_count}: Price={signal.price}, Size={position:.6f}, "
                   f"New Avg Entry={self.position_log.entry_price:.2f} (was {old_entry:.2f}), Fee={fee:.2f}")
        else:
            # Skip buying if price is higher than entry
            logger.info(f"Skipping buy: Current price {signal.price} higher than entry {self.position_log.entry_price}")
            return

        self.position_log.position += position
        self.position_log.entry_timestamp = self._convert_to_ist(signal.timestamp)
        self.trade_log.append(self.position_log)
        
        # Create and queue trade entry
        trade_entry = self._create_trade_entry(signal, "BUY", position, fee)
        self._save_trade_entry(trade_entry)
            
    def sell(self, signal: MarketSignal, trailing_stoploss: float):
        
        # First exit only on candle close signal
        if self.position_log.first_exit_price is None:
            # First exit (50% of position)
            exit_position = self.position_log.position * 0.5
            exit_value = exit_position * signal.price
            fee = exit_value * (self.fee_percent / 100)
            
            # Calculate PnL for first exit
            entry_value = exit_position * self.position_log.entry_price
            exit_pnl = (exit_value - entry_value - fee)
            self.pnl += exit_pnl
            
            # Update position
            self.position_log.position -= exit_position
            self.position_log.first_exit_price = signal.price
            self.position_log.first_exit_timestamp = self._convert_to_ist(signal.timestamp)
            self.position_log.trailing_stoploss = trailing_stoploss
            self.trade_log.append(self.position_log)
            self.buy_count = 0
            
            logger.info(f"First exit (50%): Price={signal.price}, Size={exit_position:.6f}, "
                    f"PnL={exit_pnl:.2f}, Fee={fee:.2f}, Trailing Stop={trailing_stoploss:.2f}")
            
            # Create and queue trade entry
            trade_entry = self._create_trade_entry(signal, "SELL_FIRST", exit_position, fee, exit_pnl)
            self._save_trade_entry(trade_entry)
            
        # Second exit only when trailing stoploss is hit
        elif (self.position_log.second_exit_price is None) and (signal.reason == "Trailing stoploss hit"):
            # Second exit (remaining position)
            exit_position = self.position_log.position
            exit_value = exit_position * signal.price
            fee = exit_value * (self.fee_percent / 100)
            
            # Calculate PnL for second exit
            entry_value = exit_position * self.position_log.entry_price
            exit_pnl = (exit_value - entry_value - fee)
            self.pnl += exit_pnl
            
            # Update position
            self.position_log.position = 0
            self.position_log.second_exit_price = signal.price
            self.position_log.second_exit_timestamp = self._convert_to_ist(signal.timestamp)
            self.position_log.trailing_stoploss = trailing_stoploss
            self.trade_log.append(self.position_log)
            self.total_invested = 0
            self.buy_count = 0
            self.position_log.reset()
            
            logger.info(f"Second exit (Trailing Stop): Price={signal.price}, Size={exit_position:.6f}, "
                    f"PnL={exit_pnl:.2f}, Fee={fee:.2f}, Total PnL={self.pnl:.2f}")
            
            # Create and queue trade entry
            trade_entry = self._create_trade_entry(signal, "SELL_SECOND", exit_position, fee, exit_pnl)
            self._save_trade_entry(trade_entry)
    
    def handle_candle_close(self, df: pl.DataFrame):
        """Process completed candle - compute all indicators and signals"""
        if len(df) < max(self.indicator.params.slow_length, self.stoploss.params.hhv_period) + 2:
            return
            
        latest_row = df.tail(1)
        current_price = latest_row['close'][0]
        latest_timestamp = latest_row['close_time'][0]
        
        # Compute indicators
        hist_buy, hist_sell = self.indicator.process_data(df)
        ts_array, current_ts, prev_ts = self.stoploss.process_data(df)
        
        # Cache trailing stop for real-time checks
        self.cached_trailing_stop = current_ts
        
        # Check signals
        if self.indicator.check_buy_signal(hist_buy):
            logger.info(f"Buy signal detected at candle close: Price={current_price}")
            signal = MarketSignal(
                action="BUY",
                price=current_price,
                timestamp=latest_timestamp,
                reason="Buy signal detected"
            )
            self.buy(signal)
            
        elif self.indicator.check_sell_signal(hist_sell):
            if self.position_log.position > 0:
                logger.info(f"Sell signal detected at candle close: Price={current_price}")
                signal = MarketSignal(
                    action="SELL",
                    price=current_price,
                    timestamp=latest_timestamp,
                    reason="Sell signal detected"
                )
                self.sell(signal, current_ts)
    
    def handle_price_update(self, current_price: float):
        """Check real-time price against cached trailing stop"""
        
        # Only check after first exit
        if (self.cached_trailing_stop is not None and self.position_log.first_exit_price is not None):  
            # Check if price is below cached trailing stop
            if current_price < self.cached_trailing_stop:
                signal = MarketSignal(
                    price=current_price,
                    action="SELL",
                    reason="Trailing stoploss hit",
                    timestamp=datetime.now(timezone.utc)
                )
                self.sell(signal, self.cached_trailing_stop)