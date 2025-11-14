"""
Performance Tracker for CryptoBot
Tracks trades, calculates metrics, and generates reports
"""

import json
import csv
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import os


class PerformanceTracker:
    """Tracks trading performance and calculates metrics"""

    def __init__(self, config: Dict):
        """
        Initialize performance tracker

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger("CryptoBot.Performance")

        self.trade_log_file = config.get("trade_log_file", "logs/trades.csv")
        self.performance_file = config.get("performance_file", "logs/performance.json")

        # Ensure logs directory exists
        os.makedirs(os.path.dirname(self.trade_log_file), exist_ok=True)

        # Initialize trade log if doesn't exist
        if not os.path.exists(self.trade_log_file):
            self._initialize_trade_log()

    def _initialize_trade_log(self):
        """Create trade log CSV with headers"""
        with open(self.trade_log_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'product_id', 'side', 'quantity', 'price',
                'value_usd', 'fee_usd', 'net_pnl', 'pnl_pct', 'hold_time_hours',
                'reason', 'notes'
            ])

    def log_trade(self, trade_data: Dict):
        """
        Log a trade to CSV

        Args:
            trade_data: Trade details dictionary
        """
        try:
            with open(self.trade_log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    trade_data.get('product_id', ''),
                    trade_data.get('side', ''),
                    trade_data.get('quantity', 0),
                    trade_data.get('price', 0),
                    trade_data.get('value_usd', 0),
                    trade_data.get('fee_usd', 0),
                    trade_data.get('net_pnl', 0),
                    trade_data.get('pnl_pct', 0),
                    trade_data.get('hold_time_hours', 0),
                    trade_data.get('reason', ''),
                    trade_data.get('notes', '')
                ])

            self.logger.info(f"Logged trade: {trade_data.get('side')} {trade_data.get('product_id')}")

        except Exception as e:
            self.logger.error(f"Error logging trade: {e}")

    def get_all_trades(self) -> List[Dict]:
        """Get all trades from log"""
        trades = []

        try:
            with open(self.trade_log_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    trades.append(row)

        except Exception as e:
            self.logger.error(f"Error reading trade log: {e}")

        return trades

    def calculate_metrics(self) -> Dict:
        """
        Calculate performance metrics

        Returns:
            Dictionary of metrics
        """
        trades = self.get_all_trades()

        if not trades:
            return {
                "total_trades": 0,
                "win_rate": 0,
                "profit_factor": 0,
                "total_pnl": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "max_win": 0,
                "max_loss": 0,
                "total_fees": 0
            }

        # Filter closed trades (with P&L)
        closed_trades = [t for t in trades if t.get('net_pnl')]

        total_trades = len(closed_trades)
        wins = [float(t['net_pnl']) for t in closed_trades if float(t.get('net_pnl', 0)) > 0]
        losses = [float(t['net_pnl']) for t in closed_trades if float(t.get('net_pnl', 0)) < 0]

        win_count = len(wins)
        loss_count = len(losses)

        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0

        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 0

        profit_factor = (total_wins / total_losses) if total_losses > 0 else 0

        avg_win = (total_wins / win_count) if win_count > 0 else 0
        avg_loss = (total_losses / loss_count) if loss_count > 0 else 0

        max_win = max(wins) if wins else 0
        max_loss = min(losses) if losses else 0

        total_pnl = sum([float(t.get('net_pnl', 0)) for t in closed_trades])
        total_fees = sum([float(t.get('fee_usd', 0)) for t in trades])

        return {
            "total_trades": total_trades,
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_pnl": total_pnl,
            "total_wins": total_wins,
            "total_losses": total_losses,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "max_win": max_win,
            "max_loss": max_loss,
            "total_fees": total_fees,
            "avg_hold_time": self._calculate_avg_hold_time(closed_trades)
        }

    def _calculate_avg_hold_time(self, trades: List[Dict]) -> float:
        """Calculate average hold time in hours"""
        if not trades:
            return 0

        hold_times = [float(t.get('hold_time_hours', 0)) for t in trades if t.get('hold_time_hours')]

        return sum(hold_times) / len(hold_times) if hold_times else 0

    def get_return_vs_benchmark(self, benchmark_return: float) -> Dict:
        """
        Compare bot performance to benchmark

        Args:
            benchmark_return: Benchmark return percentage

        Returns:
            Comparison metrics
        """
        metrics = self.calculate_metrics()

        initial_capital = self.config.get("initial_capital", 600.0)
        bot_return = (metrics['total_pnl'] / initial_capital) * 100

        outperformance = bot_return - benchmark_return

        return {
            "bot_return_pct": bot_return,
            "benchmark_return_pct": benchmark_return,
            "outperformance_pct": outperformance,
            "is_outperforming": outperformance > 0
        }

    def save_performance_snapshot(self):
        """Save performance snapshot to JSON"""
        try:
            metrics = self.calculate_metrics()
            metrics['timestamp'] = datetime.now().isoformat()

            # Load existing snapshots
            snapshots = []
            if os.path.exists(self.performance_file):
                with open(self.performance_file, 'r') as f:
                    data = json.load(f)
                    snapshots = data.get('snapshots', [])

            # Add new snapshot
            snapshots.append(metrics)

            # Save
            with open(self.performance_file, 'w') as f:
                json.dump({'snapshots': snapshots}, f, indent=2)

            self.logger.info("Saved performance snapshot")

        except Exception as e:
            self.logger.error(f"Error saving performance snapshot: {e}")

    def get_daily_report(self) -> Dict:
        """Generate daily performance report"""
        trades = self.get_all_trades()

        # Filter today's trades
        today = datetime.now().date()
        today_trades = [
            t for t in trades
            if datetime.fromisoformat(t['timestamp']).date() == today
        ]

        daily_pnl = sum([float(t.get('net_pnl', 0)) for t in today_trades if t.get('net_pnl')])
        daily_trades_count = len([t for t in today_trades if t.get('net_pnl')])
        daily_fees = sum([float(t.get('fee_usd', 0)) for t in today_trades])

        return {
            "date": today.isoformat(),
            "trades_count": daily_trades_count,
            "net_pnl": daily_pnl,
            "total_fees": daily_fees,
            "trades": today_trades
        }
