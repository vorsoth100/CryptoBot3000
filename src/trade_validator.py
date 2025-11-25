"""
Trade Validation Layer - Prevents catastrophic trades
Validates all trades against multiple safety checks before execution
"""

import logging
from typing import Dict, Tuple, Optional
from datetime import datetime


class TradeValidator:
    """
    Multi-layer validation system to prevent bad trades

    Validates trades against:
    1. Market regime appropriateness
    2. Screener signal alignment
    3. Technical indicator sanity checks
    4. Account size safety limits
    5. Risk concentration limits
    """

    def __init__(self, config: Dict, logger: logging.Logger = None):
        self.config = config
        self.logger = logger or logging.getLogger("CryptoBot.TradeValidator")

    def validate_trade(self,
                      action: str,
                      product_id: str,
                      recommendation: Dict,
                      screener_data: Optional[Dict] = None,
                      market_data: Optional[Dict] = None,
                      account_size: float = 0) -> Tuple[bool, str]:
        """
        Validate a trade before execution

        Args:
            action: 'buy' or 'sell'
            product_id: Coin to trade (e.g., 'ETH-USD')
            recommendation: Claude's recommendation dict
            screener_data: Latest screener results
            market_data: Current market regime data (Fear & Greed, etc.)
            account_size: Current account balance

        Returns:
            Tuple of (is_valid: bool, reason: str)
        """

        # Rule 1: NEVER buy if screener says SELL
        if action == 'buy' and screener_data:
            is_valid, reason = self._validate_screener_alignment(
                action, product_id, screener_data
            )
            if not is_valid:
                return False, f"❌ SCREENER CONFLICT: {reason}"

        # Rule 2: Check market regime appropriateness
        if market_data:
            is_valid, reason = self._validate_market_regime(
                action, recommendation, market_data
            )
            if not is_valid:
                return False, f"❌ MARKET REGIME: {reason}"

        # Rule 3: Check RSI sanity (don't buy overbought in bear markets)
        if action == 'buy' and 'rsi' in recommendation:
            is_valid, reason = self._validate_rsi_sanity(
                recommendation, market_data
            )
            if not is_valid:
                return False, f"❌ RSI CHECK: {reason}"

        # Rule 4: Emergency account size protection
        if action == 'buy':
            is_valid, reason = self._validate_account_safety(
                recommendation, account_size
            )
            if not is_valid:
                return False, f"❌ ACCOUNT SAFETY: {reason}"

        # Rule 5: Conviction threshold
        conviction = recommendation.get('conviction', recommendation.get('confidence', 0))
        min_conviction = self.config.get('claude_confidence_threshold', 80)
        if conviction < min_conviction:
            return False, f"❌ LOW CONVICTION: {conviction}% < {min_conviction}% required"

        # All checks passed
        return True, "✓ All validation checks passed"

    def _validate_screener_alignment(self,
                                    action: str,
                                    product_id: str,
                                    screener_data: Dict) -> Tuple[bool, str]:
        """
        CRITICAL: Don't buy if screener says SELL
        This is what went wrong with SUI, ETH, XRP
        """
        # Find this product in screener results
        screener_signal = None
        for opp in screener_data.get('opportunities', []):
            if opp.get('product_id') == product_id:
                screener_signal = opp.get('signal', '').lower()
                rsi = opp.get('rsi', 0)
                score = opp.get('score', 0)
                break

        if not screener_signal:
            # Product not in screener results - risky
            self.logger.warning(f"{product_id} not in screener results")
            return False, f"{product_id} not validated by screener"

        # Check for conflicts
        if action == 'buy':
            if 'sell' in screener_signal:
                return False, f"{product_id} has SELL signal ({screener_signal}), cannot BUY"

            if 'buy' not in screener_signal:
                return False, f"{product_id} has neutral/hold signal ({screener_signal}), not a BUY"

        return True, f"Screener signal aligned: {screener_signal}"

    def _validate_market_regime(self,
                               action: str,
                               recommendation: Dict,
                               market_data: Dict) -> Tuple[bool, str]:
        """
        Check if trade matches current market regime
        Don't use bull strategies in bear markets
        """
        fear_greed = market_data.get('fear_greed_index', 50)

        # Extreme Fear (< 25): Only defensive trades
        if fear_greed < 25:
            if action == 'buy':
                # In extreme fear, only buy deeply oversold with strong reversal signals
                rsi = recommendation.get('rsi', 50)
                if rsi > 40:
                    return False, f"Extreme Fear market (FGI={fear_greed}), RSI={rsi} too high for safe entry"

        # Fear (25-45): Cautious bear market trades
        elif fear_greed < 45:
            if action == 'buy':
                rsi = recommendation.get('rsi', 50)
                if rsi > 60:
                    return False, f"Bear market (FGI={fear_greed}), RSI={rsi} indicates overbought bounce"

        # Greed (55-75): Cautious bull market trades
        elif fear_greed > 75:
            if action == 'buy':
                # Extreme greed - be cautious of tops
                rsi = recommendation.get('rsi', 50)
                if rsi > 75:
                    return False, f"Extreme Greed (FGI={fear_greed}), RSI={rsi} indicates euphoric top"

        return True, f"Market regime acceptable (FGI={fear_greed})"

    def _validate_rsi_sanity(self,
                            recommendation: Dict,
                            market_data: Optional[Dict]) -> Tuple[bool, str]:
        """
        Sanity check RSI values
        CRITICAL: This is what failed with SUI (RSI=77.3), ETH (RSI=73.2), XRP (RSI=77.7)
        """
        rsi = recommendation.get('rsi', 50)
        fear_greed = market_data.get('fear_greed_index', 50) if market_data else 50

        # In bear markets (FGI < 45), high RSI is a SELL signal, not BUY
        if fear_greed < 45:
            if rsi > 70:
                return False, f"Bear market + RSI={rsi:.1f} = OVERBOUGHT BOUNCE (don't buy tops!)"
            if rsi > 60:
                self.logger.warning(f"Elevated RSI={rsi:.1f} in bear market - risky entry")

        # Even in bull markets, RSI > 80 is dangerous
        if rsi > 80:
            return False, f"Extreme overbought RSI={rsi:.1f} - high probability of reversal"

        return True, f"RSI={rsi:.1f} acceptable"

    def _validate_account_safety(self,
                                recommendation: Dict,
                                account_size: float) -> Tuple[bool, str]:
        """
        Emergency protection for small accounts
        If account < $500, use ultra-conservative rules
        """
        if account_size < 500:
            # CRITICAL: Account in danger zone
            conviction = recommendation.get('conviction', recommendation.get('confidence', 0))

            # Require extremely high conviction
            if conviction < 90:
                return False, f"Small account (${account_size:.0f}) requires >90% conviction (got {conviction}%)"

            # Only top-tier coins
            product_id = recommendation.get('coin', '')
            safe_coins = ['BTC-USD', 'ETH-USD', 'SOL-USD']
            if product_id not in safe_coins:
                return False, f"Small account should only trade {safe_coins}, not {product_id}"

        return True, f"Account size ${account_size:.0f} check passed"

    def should_close_position_early(self,
                                    product_id: str,
                                    entry_price: float,
                                    current_price: float,
                                    market_data: Optional[Dict] = None) -> Tuple[bool, str]:
        """
        Check if we should close a position early (before stop loss)
        due to changed market conditions
        """
        current_pnl_pct = ((current_price - entry_price) / entry_price) * 100

        # If we're in profit in a bear market, take it
        if market_data and market_data.get('fear_greed_index', 50) < 30:
            if current_pnl_pct > 3:
                return True, f"Bear market + {current_pnl_pct:.1f}% profit = TAKE IT!"

        # If we're in small profit but RSI turning overbought
        if 'rsi' in market_data and market_data['rsi'] > 75:
            if current_pnl_pct > 1:
                return True, f"RSI overbought ({market_data['rsi']:.1f}) + small profit = EXIT"

        return False, "Hold position"
