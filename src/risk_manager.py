"""
Risk Manager for CryptoBot
Handles position sizing, stop losses, and risk controls
"""

import logging
import os
import json
import shutil
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from src.utils import calculate_fees, calculate_position_size, calculate_break_even_price


class Position:
    """Represents an open trading position"""

    def __init__(self, product_id: str, quantity: float, entry_price: float,
                 entry_fee: float, timestamp: datetime):
        """
        Initialize position

        Args:
            product_id: Product ID (e.g., BTC-USD)
            quantity: Position quantity
            entry_price: Entry price
            entry_fee: Fee paid on entry
            timestamp: Entry timestamp
        """
        self.product_id = product_id
        self.quantity = quantity
        self.entry_price = entry_price
        self.entry_fee = entry_fee
        self.timestamp = timestamp

        # Track partial profits
        self.tp_hit = [False, False, False]  # Track which TP levels hit
        self.original_quantity = quantity

        # Track peak for trailing stop
        self.peak_price = entry_price
        self.peak_pnl_pct = 0.0


class RiskManager:
    """Manages trading risk and position sizing"""

    def __init__(self, config: Dict):
        """
        Initialize risk manager

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger("CryptoBot.RiskManager")

        # Position persistence file
        self.positions_file = config.get("positions_file", "data/positions.json")
        os.makedirs(os.path.dirname(self.positions_file), exist_ok=True)

        # Track positions
        self.positions: Dict[str, Position] = {}

        # Load existing positions from file
        self._load_positions()

        # Track simulated capital (for dry run mode)
        self.current_capital = config.get("initial_capital", 600.0)
        self.initial_capital = self.current_capital

        # Track daily metrics
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.total_drawdown = 0.0

    def calculate_position_size_usd(self, balance: float) -> float:
        """
        Calculate position size in USD

        Args:
            balance: Available balance

        Returns:
            Position size in USD
        """
        position_pct = self.config.get("max_position_pct", 0.25)
        maker_fee = self.config.get("coinbase_maker_fee", 0.005)
        taker_fee = self.config.get("coinbase_taker_fee", 0.02)

        size = calculate_position_size(balance, position_pct, maker_fee, taker_fee)

        return size

    def can_open_position(self, product_id: str, size_usd: float, balance: float) -> Tuple[bool, str]:
        """
        Check if new position can be opened

        Args:
            product_id: Product to trade
            size_usd: Position size in USD
            balance: Available balance

        Returns:
            Tuple of (can_open, reason)
        """
        # Check if already have position
        if product_id in self.positions:
            return False, f"Already have position in {product_id}"

        # Check position count
        max_positions = self.config.get("max_positions", 3)
        if len(self.positions) >= max_positions:
            return False, f"Max positions ({max_positions}) reached"

        # Check minimum trade size
        min_trade_usd = self.config.get("min_trade_usd", 150.0)
        if size_usd < min_trade_usd:
            return False, f"Trade size ${size_usd:.2f} below minimum ${min_trade_usd}"

        # Check max position percentage
        max_position_pct = self.config.get("max_position_pct", 0.25)
        if size_usd > balance * max_position_pct:
            return False, f"Trade size exceeds {max_position_pct * 100}% of balance"

        # Check fees
        maker_fee = self.config.get("coinbase_maker_fee", 0.005)
        taker_fee = self.config.get("coinbase_taker_fee", 0.02)
        max_fee_pct = self.config.get("max_fee_pct", 0.01)

        # Calculate fees (round-trip)
        total_fees = size_usd * (maker_fee + taker_fee)
        fee_pct = total_fees / size_usd

        if fee_pct > max_fee_pct:
            return False, f"Fees ({fee_pct * 100:.2f}%) exceed max ({max_fee_pct * 100}%)"

        # Check drawdown limit
        max_drawdown = self.config.get("max_drawdown_pct", 0.20)
        if self.total_drawdown >= max_drawdown:
            return False, f"Max drawdown ({max_drawdown * 100}%) reached - trading paused"

        # Check daily loss limit
        max_daily_loss_pct = self.config.get("max_daily_loss_pct", 0.05)
        initial_capital = self.config.get("initial_capital", 600.0)
        max_daily_loss_usd = initial_capital * max_daily_loss_pct

        if self.daily_pnl <= -max_daily_loss_usd:
            return False, f"Daily loss limit (${max_daily_loss_usd:.2f}) reached"

        return True, "OK"

    def open_position(self, product_id: str, quantity: float, entry_price: float,
                     entry_fee: float) -> bool:
        """
        Open a new position

        Args:
            product_id: Product ID
            quantity: Position quantity
            entry_price: Entry price
            entry_fee: Fee paid

        Returns:
            True if successful
        """
        if product_id in self.positions:
            self.logger.error(f"Position already exists for {product_id}")
            return False

        position = Position(
            product_id=product_id,
            quantity=quantity,
            entry_price=entry_price,
            entry_fee=entry_fee,
            timestamp=datetime.now()
        )

        self.positions[product_id] = position

        # Deduct cost from simulated capital (entry cost + fees)
        position_cost = (quantity * entry_price) + entry_fee
        self.current_capital -= position_cost

        self.logger.info(
            f"[POSITION] Opened {product_id}: {quantity} @ ${entry_price:.2f} "
            f"(fee: ${entry_fee:.2f}) | Remaining capital: ${self.current_capital:.2f}"
        )

        # Save positions to disk
        self._save_positions()

        return True

    def close_position(self, product_id: str, exit_price: float,
                      exit_fee: float, reason: str = "") -> Optional[Dict]:
        """
        Close a position

        Args:
            product_id: Product ID
            exit_price: Exit price
            exit_fee: Fee paid on exit
            reason: Reason for closing

        Returns:
            P&L details or None
        """
        if product_id not in self.positions:
            self.logger.error(f"No position found for {product_id}")
            return None

        position = self.positions[product_id]

        # Calculate P&L
        entry_value = position.entry_price * position.quantity
        exit_value = exit_price * position.quantity
        gross_pnl = exit_value - entry_value
        total_fees = position.entry_fee + exit_fee
        net_pnl = gross_pnl - total_fees
        pnl_pct = (net_pnl / (entry_value + position.entry_fee)) * 100

        pnl_details = {
            "product_id": product_id,
            "quantity": position.quantity,
            "entry_price": position.entry_price,
            "exit_price": exit_price,
            "entry_value": entry_value,
            "exit_value": exit_value,
            "gross_pnl": gross_pnl,
            "total_fees": total_fees,
            "net_pnl": net_pnl,
            "pnl_pct": pnl_pct,
            "hold_time": (datetime.now() - position.timestamp).total_seconds() / 3600,  # hours
            "reason": reason
        }

        # Add proceeds back to simulated capital (exit value - fees)
        proceeds = exit_value - exit_fee
        self.current_capital += proceeds

        # Update daily P&L
        self.daily_pnl += net_pnl
        self.daily_trades += 1

        # Update drawdown if loss
        if net_pnl < 0:
            loss_pct = abs(net_pnl) / self.initial_capital
            self.total_drawdown += loss_pct

        # Remove position
        del self.positions[product_id]

        # Save positions to disk
        self._save_positions()

        self.logger.info(
            f"[POSITION] Closed {product_id}: ${net_pnl:.2f} ({pnl_pct:.2f}%) - {reason} "
            f"| Current capital: ${self.current_capital:.2f}"
        )

        return pnl_details

    def check_exit_signals(self, product_id: str, current_price: float) -> Optional[Tuple[str, str]]:
        """
        Check if position should be exited

        Args:
            product_id: Product ID
            current_price: Current price

        Returns:
            Tuple of (action, reason) or None
        """
        if product_id not in self.positions:
            return None

        position = self.positions[product_id]

        # Calculate current P&L %
        pnl_pct = (current_price - position.entry_price) / position.entry_price

        # 1. Check stop loss
        stop_loss_pct = self.config.get("stop_loss_pct", 0.06)
        if pnl_pct <= -stop_loss_pct:
            return ("STOP_LOSS", f"Hit stop loss at {pnl_pct * 100:.2f}%")

        # 2. Check take profit
        take_profit_pct = self.config.get("take_profit_pct", 0.10)
        if pnl_pct >= take_profit_pct:
            # Check if partial profit enabled
            if self.config.get("partial_profit_enabled", True):
                return self._check_partial_profits(position, pnl_pct)
            else:
                return ("TAKE_PROFIT", f"Hit take profit at {pnl_pct * 100:.2f}%")

        # 3. Check trailing stop
        if self.config.get("trailing_stop_enabled", True):
            trailing_action = self._check_trailing_stop(position, current_price, pnl_pct)
            if trailing_action:
                return trailing_action

        return None

    def _check_partial_profits(self, position: Position, pnl_pct: float) -> Optional[Tuple[str, str]]:
        """Check partial profit levels"""
        levels = self.config.get("partial_profit_levels", [0.10, 0.20, 0.30])
        amounts = self.config.get("partial_profit_amounts", [0.33, 0.33, 0.34])

        for i, level in enumerate(levels):
            if pnl_pct >= level and not position.tp_hit[i]:
                position.tp_hit[i] = True
                amount_pct = amounts[i]
                return ("PARTIAL_PROFIT", f"Take {amount_pct * 100:.0f}% profit at +{level * 100:.0f}%")

        # If all levels hit, close remaining
        if all(position.tp_hit):
            return ("TAKE_PROFIT", "All partial profit levels hit")

        return None

    def _check_trailing_stop(self, position: Position, current_price: float,
                            pnl_pct: float) -> Optional[Tuple[str, str]]:
        """Check trailing stop"""
        activation_pct = self.config.get("trailing_stop_activation_pct", 0.10)
        distance_pct = self.config.get("trailing_stop_distance_pct", 0.05)

        # Only activate trailing stop after reaching activation threshold
        if pnl_pct >= activation_pct:
            # Update peak
            if current_price > position.peak_price:
                position.peak_price = current_price
                position.peak_pnl_pct = pnl_pct

            # Check if price dropped from peak
            drop_from_peak = (position.peak_price - current_price) / position.peak_price

            if drop_from_peak >= distance_pct:
                return ("TRAILING_STOP", f"Trailing stop triggered (drop {drop_from_peak * 100:.2f}% from peak)")

        return None

    def get_stop_loss_price(self, product_id: str) -> Optional[float]:
        """Get stop loss price for position"""
        if product_id not in self.positions:
            return None

        position = self.positions[product_id]
        stop_loss_pct = self.config.get("stop_loss_pct", 0.06)

        return position.entry_price * (1 - stop_loss_pct)

    def get_take_profit_price(self, product_id: str) -> Optional[float]:
        """Get take profit price for position"""
        if product_id not in self.positions:
            return None

        position = self.positions[product_id]
        take_profit_pct = self.config.get("take_profit_pct", 0.10)

        return position.entry_price * (1 + take_profit_pct)

    def get_break_even_price(self, product_id: str) -> Optional[float]:
        """Get break-even price for position"""
        if product_id not in self.positions:
            return None

        position = self.positions[product_id]
        maker_fee = self.config.get("coinbase_maker_fee", 0.006)
        taker_fee = self.config.get("coinbase_taker_fee", 0.008)

        return calculate_break_even_price(position.entry_price, maker_fee, taker_fee)

    def get_position_pnl(self, product_id: str, current_price: float) -> Optional[Dict]:
        """
        Get current P&L for position

        Args:
            product_id: Product ID
            current_price: Current price

        Returns:
            P&L details
        """
        if product_id not in self.positions:
            return None

        position = self.positions[product_id]

        entry_value = position.entry_price * position.quantity
        current_value = current_price * position.quantity
        gross_pnl = current_value - entry_value

        # Estimate exit fee
        taker_fee = self.config.get("coinbase_taker_fee", 0.008)
        exit_fee = current_value * taker_fee

        total_fees = position.entry_fee + exit_fee
        net_pnl = gross_pnl - total_fees
        pnl_pct = (net_pnl / (entry_value + position.entry_fee)) * 100

        return {
            "product_id": product_id,
            "quantity": position.quantity,
            "entry_price": position.entry_price,
            "current_price": current_price,
            "entry_value": entry_value,
            "current_value": current_value,
            "gross_pnl": gross_pnl,
            "total_fees": total_fees,
            "net_pnl": net_pnl,
            "pnl_pct": pnl_pct,
            "stop_loss_price": self.get_stop_loss_price(product_id),
            "take_profit_price": self.get_take_profit_price(product_id),
            "break_even_price": self.get_break_even_price(product_id)
        }

    def get_all_positions(self) -> List[Dict]:
        """Get list of all open positions"""
        return [
            {
                "product_id": pos.product_id,
                "quantity": pos.quantity,
                "entry_price": pos.entry_price,
                "entry_fee": pos.entry_fee,
                "timestamp": pos.timestamp.isoformat()
            }
            for pos in self.positions.values()
        ]

    def reset_daily_metrics(self):
        """Reset daily P&L and trade count"""
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.logger.info("Reset daily metrics")

    def _load_positions(self):
        """Load positions and capital state from disk"""
        try:
            if os.path.exists(self.positions_file):
                with open(self.positions_file, 'r') as f:
                    data = json.load(f)

                # Load metadata (capital state) if it exists
                if '_metadata' in data:
                    metadata = data['_metadata']
                    self.current_capital = metadata.get('current_capital', self.current_capital)
                    self.daily_pnl = metadata.get('daily_pnl', 0.0)
                    self.daily_trades = metadata.get('daily_trades', 0)
                    self.total_drawdown = metadata.get('total_drawdown', 0.0)
                    self.logger.info(f"Restored capital state: ${self.current_capital:.2f} (Initial: ${self.initial_capital:.2f})")
                    positions_data = data.get('positions', {})
                else:
                    # Legacy format (positions only, no metadata)
                    # Create backup before migration
                    backup_file = self.positions_file + '.backup'
                    shutil.copy2(self.positions_file, backup_file)
                    self.logger.warning(f"Loading legacy position format without capital state. Backup saved to {backup_file}")
                    self.logger.warning("Calculating capital based on positions and initial_capital")
                    positions_data = data

                # Load positions
                total_position_value = 0.0
                for product_id, pos_data in positions_data.items():
                    # Recreate Position objects
                    position = Position(
                        product_id=pos_data['product_id'],
                        quantity=pos_data['quantity'],
                        entry_price=pos_data['entry_price'],
                        entry_fee=pos_data['entry_fee'],
                        timestamp=datetime.fromisoformat(pos_data['entry_time'])
                    )
                    self.positions[product_id] = position

                    # Calculate total capital locked in positions
                    entry_value = position.quantity * position.entry_price
                    total_position_value += (entry_value + position.entry_fee)

                # If loading legacy format, calculate current_capital
                if '_metadata' not in data and len(self.positions) > 0:
                    # Capital = initial_capital - money locked in positions
                    self.current_capital = self.initial_capital - total_position_value
                    self.logger.info(f"Migrated from legacy format: Initial=${self.initial_capital:.2f}, Locked in positions=${total_position_value:.2f}, Available=${self.current_capital:.2f}")
                    # Save in new format immediately
                    self._save_positions()
                    self.logger.info(f"Migrated to new format with metadata")

                self.logger.info(f"Loaded {len(self.positions)} positions from {self.positions_file}")
        except Exception as e:
            self.logger.error(f"Error loading positions: {e}")

    def _save_positions(self):
        """Save positions and capital state to disk"""
        try:
            data = {
                '_metadata': {
                    'current_capital': self.current_capital,
                    'initial_capital': self.initial_capital,
                    'daily_pnl': self.daily_pnl,
                    'daily_trades': self.daily_trades,
                    'total_drawdown': self.total_drawdown,
                    'last_updated': datetime.now().isoformat()
                },
                'positions': {}
            }

            for product_id, pos in self.positions.items():
                data['positions'][product_id] = {
                    'product_id': pos.product_id,
                    'quantity': pos.quantity,
                    'entry_price': pos.entry_price,
                    'entry_fee': pos.entry_fee,
                    'entry_time': pos.timestamp.isoformat()
                }

            with open(self.positions_file, 'w') as f:
                json.dump(data, f, indent=2)

            self.logger.debug(f"Saved {len(self.positions)} positions and capital state (${self.current_capital:.2f}) to {self.positions_file}")
        except Exception as e:
            self.logger.error(f"Error saving positions: {e}")
