import queue
import logging
import json, threading
from datetime import datetime
from typing import Optional, Dict, List
from datetime import datetime, timedelta, timezone
from erendil.models.data_models import MarketSignal
from erendil.trading.position import PositionManager
from erendil.trading.analyzer import EnhancedMarketAnalyzer


logger = logging.getLogger(__name__)


class TradeLogWorker:
    def __init__(self, log_file: str):
        self.log_file = log_file
        self.queue = queue.Queue()
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()
        
    def _process_queue(self):
        """Background worker that processes the queue and saves trades"""
        while self.is_running:
            try:
                # Wait for new trades with a timeout to allow checking is_running
                trade_entry = self.queue.get(timeout=1.0)
                
                try:
                    # Read existing trades
                    try:
                        with open(self.log_file, 'r') as f:
                            content = f.read()
                            trades = json.loads(content) if content else []
                    except FileNotFoundError:
                        trades = []

                    # Append new trade
                    trades.append(trade_entry)

                    # Write updated trades back to file
                    with open(self.log_file, 'w') as f:
                        json.dump(trades, f, indent=2, default=str)
                        
                except Exception as e:
                    logger.error(f"Error saving trade log: {e}")
                
                self.queue.task_done()
                
            except queue.Empty:
                continue  # No trades to process, continue waiting
            except Exception as e:
                logger.error(f"Error in trade log worker: {e}")
                
    def add_trade(self, trade_entry: Dict):
        """Add a trade entry to the processing queue"""
        self.queue.put(trade_entry)
        
    def stop(self):
        """Stop the worker thread"""
        self.is_running = False
        self.worker_thread.join()
        
    def wait_until_done(self):
        """Wait for all queued trades to be processed"""
        self.queue.join()
        

class TradeManager:
    def __init__(self, analyzer: EnhancedMarketAnalyzer, capital_per_trade: float=100, fee_percent: float=0.1, max_buys: int=3, log_file: str = "trade_log.json"):
        self.pnl = 0
        self.buy_count = 0
        self.trade_log = []
        self.total_invested = 0
        self.analyzer = analyzer
        self.max_buys = max_buys
        self.fee_percent = fee_percent
        self.position_log = PositionManager()
        self.capital_per_trade = capital_per_trade
        
        self.log_worker = TradeLogWorker(log_file)
        
    def _convert_to_ist(self, utc_time: datetime) -> datetime:
        ist = timezone(timedelta(hours=5, minutes=30))
        return utc_time.astimezone(ist)
    
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
        trade_entry = self._create_trade_entry(signal, f"BUY", position, fee)
        self.log_worker.add_trade(trade_entry)
            
    
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
            self.log_worker.add_trade(trade_entry)
            
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
            self.log_worker.add_trade(trade_entry)
    
    def handle_candle_close(self, df):
        signal, trailing_stoploss = self.analyzer.calculate_signals(df)
        if signal:
            if signal.action == "BUY":
                logger.info(f"Buy signal detected at candle close: Price={signal.price}")
                self.buy(signal)
            elif (signal.action == "SELL") and (signal.reason == "Sell signal detected"):
                if self.position_log.position > 0:
                    logger.info(f"Sell signal detected at candle close: Price={signal.price}")
                    self.sell(signal, trailing_stoploss)
    
    def handle_price_update(self, df):
        signal, trailing_stoploss = self.analyzer.calculate_signals(df)
        if signal:
            if (signal.action == "SELL") and (signal.reason == "Trailing stoploss hit"):
                if self.position_log.first_exit_price is not None:
                    logger.info(f"Trailing stop triggered at price {signal.price}")
                    self.sell(signal, trailing_stoploss)
                    
    def cleanup(self):
        """Clean up resources before shutting down"""
        # Wait for all pending trades to be saved
        self.log_worker.wait_until_done()
        # Stop the worker thread
        self.log_worker.stop()