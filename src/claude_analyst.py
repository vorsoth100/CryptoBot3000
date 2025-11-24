"""
Claude AI Analyst for CryptoBot
Uses Anthropic Claude API for market analysis and trade recommendations
"""

import os
import json
import logging
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime
from anthropic import Anthropic


def convert_numpy_types(obj: Any) -> Any:
    """
    Recursively convert numpy types to native Python types for JSON serialization

    Args:
        obj: Object that may contain numpy types

    Returns:
        Object with numpy types converted to Python types
    """
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    else:
        return obj


class ClaudeAnalyst:
    """Claude AI analyst for crypto market analysis"""

    def __init__(self, config: Dict, api_key: Optional[str] = None):
        """
        Initialize Claude analyst

        Args:
            config: Configuration dictionary
            api_key: Anthropic API key (or from env)
        """
        self.config = config
        self.logger = logging.getLogger("CryptoBot.Claude")

        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            self.logger.warning("Anthropic API key not set")
            self.client = None
        else:
            try:
                # Initialize Anthropic client
                # For anthropic>=0.39.0, proxies parameter is not supported
                self.client = Anthropic(api_key=api_key)
                self.logger.info("Claude API client initialized successfully")
            except Exception as e:
                self.logger.error(f"Failed to initialize Claude client: {e}")
                self.client = None

        self.model = config.get("claude_model", "claude-sonnet-4-5-20250929")

    def analyze_market(self, market_context: Dict) -> Optional[Dict]:
        """
        Analyze market conditions and provide recommendations

        Args:
            market_context: Dictionary with market data, portfolio, etc.

        Returns:
            Analysis results with recommendations
        """
        if not self.client:
            self.logger.error("Claude client not initialized")
            return None

        try:
            prompt = self._build_analysis_prompt(market_context)

            self.logger.info("Requesting Claude market analysis...")

            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Parse response
            content = response.content[0].text

            # Try to parse JSON response
            try:
                analysis = json.loads(content)
            except json.JSONDecodeError:
                # If not JSON, wrap in structure
                analysis = {
                    "raw_analysis": content,
                    "timestamp": datetime.now().isoformat()
                }

            # Log analysis
            self._log_analysis(analysis)

            self.logger.info("Claude analysis completed")

            return analysis

        except Exception as e:
            self.logger.error(f"Error getting Claude analysis: {e}")
            return None

    def _get_strategy_prompt(self, strategy: str) -> str:
        """Get strategy-specific prompt section"""

        strategies = {
            'momentum_bull': {
                'goal': 'MOMENTUM BULL MARKET: Ride hot coins with strong uptrends',
                'strategy': '''**TRADING STRATEGY (MOMENTUM BULL):**
- PRIORITY: Identify coins with explosive momentum (volume spikes + strong gains)
- Look for coins up 10-20% in 24h with 2x+ volume (catching the wave early)
- Prefer coins breaking resistance levels with high volume confirmation
- Enter on strength with tight trailing stops to lock in gains
- Target quick 15-30% gains, exit on first sign of weakness
- RSI can be 70+ (momentum is king in bull markets)

**WHAT MAKES A GOOD TRADE:**
- Coin up 10-20% in 24h (strong momentum, not parabolic yet)
- Volume 3x+ average (institutional/whale accumulation)
- Breaking above previous resistance with conviction
- Positive news catalyst or trending on social media
- Technical signal: STRONG_BUY with high volume
- RSI 60-80 (strong momentum, room to run)''',
                'targets': '15% (TP1), 25% (TP2), 35% (TP3)',
                'stop_loss': '5% below entry (tight stops for momentum)',
                'position_size': '20-30% of capital (aggressive in bull markets)',
                'conviction_threshold': 75
            },

            'bear_survival': {
                'goal': 'BEAR MARKET SURVIVAL: Preserve capital and catch quick bounces',
                'strategy': '''**TRADING STRATEGY (BEAR SURVIVAL):**
- PRIORITY: Capital preservation first, opportunistic bounces second
- Look for oversold coins (RSI <25) with volume capitulation
- Wait for signs of reversal: bullish divergence, hammer candles, volume spike
- Enter ONLY on confirmed bounce with tight stops
- Target quick 5-10% gains, exit immediately on weakness
- Avoid falling knives - wait for price stabilization first

**WHAT MAKES A GOOD TRADE:**
- Coin down 20-30% in recent days (extreme oversold)
- RSI <25 with bullish divergence forming
- Volume spike on green candle (buyers stepping in)
- Bouncing off major support level (previous low, MA200)
- First green day after 5+ red days
- News sentiment improving from very negative to neutral''',
                'targets': '5% (TP1), 8% (TP2), 12% (TP3)',
                'stop_loss': '4% below entry (very tight in bear markets)',
                'position_size': '10-15% of capital (defensive sizing)',
                'conviction_threshold': 85
            },

            'range_scalping': {
                'goal': 'RANGE TRADING: Scalp bounces in sideways/choppy markets',
                'strategy': '''**TRADING STRATEGY (RANGE SCALPING):**
- PRIORITY: Buy support, sell resistance in established ranges
- Identify coins in clear consolidation (trading in 10-15% range for 7+ days)
- Enter near bottom of range (support + oversold RSI)
- Exit near top of range (resistance + overbought RSI)
- Target quick 3-8% moves, multiple trades per day
- Avoid range breakouts - stick to the pattern

**WHAT MAKES A GOOD TRADE:**
- Coin trading in clear range for 7+ days
- Price near support (bottom 20% of range)
- RSI <35 at support, or RSI >65 at resistance
- Volume decreasing (consolidation, not distribution)
- Bollinger Bands squeezing (low volatility, mean reversion likely)
- Clear support/resistance levels visible on chart''',
                'targets': '3% (TP1), 5% (TP2), 8% (TP3)',
                'stop_loss': '3% below support (or above resistance for shorts)',
                'position_size': '15-20% of capital (moderate risk)',
                'conviction_threshold': 70
            },

            'breakout_hunter': {
                'goal': 'BREAKOUT HUNTING: Catch explosive moves from consolidation',
                'strategy': '''**TRADING STRATEGY (BREAKOUT HUNTING):**
- PRIORITY: Identify coins breaking out of consolidation with volume
- Look for consolidation patterns: triangles, flags, pennants (7+ days)
- Wait for breakout above resistance with 2x+ volume spike
- Enter on breakout or first pullback to broken resistance (now support)
- Target 20-40% moves to next major resistance
- Use trailing stops to ride the move

**WHAT MAKES A GOOD TRADE:**
- Coin consolidating in tight range for 10+ days
- Breaking above resistance with 3x+ volume spike
- No major resistance overhead (clear path higher)
- Positive news catalyst or sector rotation
- Technical signal: STRONG_BUY with volume confirmation
- RSI breaking above 60 (momentum shift confirmed)''',
                'targets': '12% (TP1), 25% (TP2), 40% (TP3)',
                'stop_loss': '6% below breakout level',
                'position_size': '20-25% of capital (aggressive on confirmed breakouts)',
                'conviction_threshold': 80
            },

            'dip_buying': {
                'goal': 'DIP BUYING: Buy panic sells in quality coins',
                'strategy': '''**TRADING STRATEGY (DIP BUYING):**
- PRIORITY: Buy quality coins during irrational panic selling
- Focus on established coins (BTC, ETH, top 20 by market cap)
- Look for 15-25% drops on no fundamental news (market-wide panic)
- Wait for volume capitulation (selling exhaustion)
- Enter when RSI <20 and price hits major support
- Target return to mean (pre-dump levels)

**WHAT MAKES A GOOD TRADE:**
- Quality coin (top 50 market cap) down 20%+ in 24-48h
- No negative fundamental news (just market panic)
- RSI <20 with bullish divergence starting
- Hitting major support: MA200, previous major low
- Volume spike on selling (capitulation, not start of dump)
- Fear & Greed Index <20 (extreme fear)''',
                'targets': '10% (TP1), 18% (TP2), 25% (TP3)',
                'stop_loss': '8% below entry (panic can continue)',
                'position_size': '15-20% of capital (quality coins only)',
                'conviction_threshold': 80
            },

            'conservative': {
                'goal': 'CONSERVATIVE APPROACH: High probability, low risk trades only',
                'strategy': '''**TRADING STRATEGY (CONSERVATIVE):**
- PRIORITY: Capital preservation and consistent small gains
- Only trade top 10 coins by market cap (BTC, ETH, BNB, etc)
- Multiple confirmations required: technicals + news + volume
- Enter only with strong confluence of signals
- Target modest 8-15% gains per trade
- Use wide stops to avoid noise (8-10%)

**WHAT MAKES A GOOD TRADE:**
- Top 10 coin with clear technical setup
- All indicators aligned: RSI, MACD, MA crossover
- Positive or neutral news sentiment (>0%)
- Volume confirming direction (2x+ on breakout)
- Clear support/resistance levels for entry/exit
- Risk/reward ratio >2:1 minimum''',
                'targets': '8% (TP1), 12% (TP2), 18% (TP3)',
                'stop_loss': '8% below entry (wide stops for patience)',
                'position_size': '15-20% of capital (never >25%)',
                'conviction_threshold': 85
            }
        }

        return strategies.get(strategy, strategies['momentum_bull'])

    def _build_analysis_prompt(self, context: Dict) -> str:
        """Build analysis prompt from context"""

        # Convert all numpy types to native Python types for JSON serialization
        clean_context = convert_numpy_types(context)

        portfolio = clean_context.get('portfolio', {})
        initial_capital = portfolio.get('initial_capital', self.config.get('initial_capital', 600))
        total_value = portfolio.get('total_value', portfolio.get('balance_usd', 0))
        balance_usd = portfolio.get('balance_usd', 0)
        positions_value = portfolio.get('positions_value', 0)

        # Calculate actual P&L
        total_pnl = total_value - initial_capital
        total_pnl_pct = (total_pnl / initial_capital * 100) if initial_capital > 0 else 0

        # Get selected prompt strategy
        prompt_strategy = self.config.get('claude_prompt_strategy', 'momentum_bull')

        # Build the strategy-specific section
        strategy_info = self._get_strategy_prompt(prompt_strategy)

        prompt = f"""You are an expert cryptocurrency trader managing a bot with ${initial_capital:.2f} initial capital on Coinbase Advanced Trade.

**YOUR PRIMARY GOAL: {strategy_info['goal']}**

{strategy_info['strategy']}

**CRITICAL CONSTRAINTS:**
- Initial Capital: ${initial_capital:.2f} USD
- Fees: {self.config.get('coinbase_maker_fee', 0.005) * 100}% maker, {self.config.get('coinbase_taker_fee', 0.02) * 100}% taker
- Minimum profit needed: 8% to justify trade after fees
- Maximum {self.config.get('max_positions', 3)} positions
- Stop loss: {self.config.get('stop_loss_pct', 0.06) * 100}% per position
- Maximum drawdown: {self.config.get('max_drawdown_pct', 0.20) * 100}%
- Risk tolerance: {self.config.get('claude_risk_tolerance', 'moderate')}

**CURRENT PORTFOLIO STATUS:**
- Available Capital: ${balance_usd:.2f} USD
- Locked in Open Positions: ${positions_value:.2f} USD
- TOTAL Portfolio Value: ${total_value:.2f} USD
- Overall P&L: ${total_pnl:+.2f} USD ({total_pnl_pct:+.2f}%)
- Open Positions: {portfolio.get('position_count', 0)}

**CURRENT PORTFOLIO:**
{json.dumps(clean_context.get('portfolio', {}), indent=2)}

**MARKET DATA:**
{json.dumps(clean_context.get('market_data', {}), indent=2)}

**TECHNICAL INDICATORS:**
{json.dumps(clean_context.get('indicators', {}), indent=2)}

**SCREENER RESULTS:**
{json.dumps(clean_context.get('screener_results', []), indent=2)}

Note: Each screener result includes technical indicators (RSI, MACD, Bollinger Bands, volume analysis) in the 'indicators' field.

**FEAR & GREED INDEX:** {clean_context.get('fear_greed', {}).get('value', 'N/A')} ({clean_context.get('fear_greed', {}).get('classification', 'N/A')})
**BTC DOMINANCE:** {clean_context.get('btc_dominance', 'N/A')}%
**TRENDING COINS (CoinGecko):** {', '.join(clean_context.get('trending_coins', [])) if clean_context.get('trending_coins') else 'N/A'}

**NEWS SENTIMENT (Last 24h):**
{clean_context.get('market_news_summary', 'No news data available')}

**COIN-SPECIFIC NEWS SENTIMENT:**
{json.dumps(clean_context.get('news_sentiment', {}), indent=2)}

Note: News sentiment scores range from -100 (very bearish) to +100 (very bullish). Scores below -30 indicate significant negative news that may impact price. Scores above +50 with "trending" flag indicate strong positive catalyst.

**RECENT TRADES:**
{json.dumps(clean_context.get('recent_trades', []), indent=2)}

**PERFORMANCE METRICS:**
{json.dumps(clean_context.get('performance', {}), indent=2)}

**YOUR TASK:**
Provide a comprehensive analysis in JSON format with:

1. **market_assessment:**
   - regime: "bull" | "bear" | "sideways"
   - confidence: 0-100
   - key_factors: [list of factors]
   - risk_level: "low" | "medium" | "high"

2. **recommended_actions:** [
   {{
     "action": "buy" | "sell" | "hold",
     "coin": "BTC-USD", etc.,
     "reasoning": "Why this trade?",
     "conviction": 0-100,
     "target_entry": price,
     "stop_loss": price,
     "take_profit": [prices],
     "position_size_pct": 0.15-0.25
   }}
]

3. **risk_warnings:** [
   "Warning message if any concerns"
]

4. **config_suggestions:** [
   {{
     "parameter": "stop_loss_pct",
     "current_value": 0.06,
     "suggested_value": 0.07,
     "reasoning": "Why change?"
   }}
]

**DECISION-MAKING FRAMEWORK FOR THIS STRATEGY:**
1. **SCAN SCREENER RESULTS** - Look for coins matching the strategy criteria above
2. **CHECK NEWS SENTIMENT** - Avoid coins with negative news (<-30%), favor coins with positive catalysts (>+50%)
3. **CONVICTION THRESHOLD** - Only recommend trades with >{strategy_info['conviction_threshold']}% conviction
4. **POSITION SIZING** - {strategy_info['position_size']}
5. **PROFIT TARGETS** - {strategy_info['targets']}
6. **STOP LOSS** - {strategy_info['stop_loss']}

**NEWS SENTIMENT GUIDELINES:**
- AVOID coins with sentiment < -30% (negative news risk)
- CAUTION on coins with sentiment -30% to 0% (neutral but watch for deterioration)
- FAVORABLE coins with sentiment 0% to +30% (neutral to slightly positive)
- STRONG BUY candidates with sentiment > +50% AND "trending" flag (positive catalyst + momentum)

**IMPORTANT RULES:**
- Factor in fees: 8% move = ~6% net profit after 2% taker fees
- Prefer high liquidity coins (BTC, ETH, SOL) for large positions
- For smaller alts, reduce position size to 15% of capital
- If market regime is clearly bearish AND no strong momentum plays, suggest HOLD
- If current drawdown >{self.config.get('max_drawdown_pct', 0.20) * 0.75 * 100}%, reduce position sizes by 50%
- You're in {self.config.get('claude_analysis_mode', 'semi_autonomous').upper()} mode
- Follow the strategy guidelines above for this specific market regime

Return ONLY valid JSON, no additional text."""

        return prompt

    def _log_analysis(self, analysis: Dict):
        """Log analysis to file"""
        try:
            log_file = self.config.get("claude_log_file", "logs/claude_analysis.log")
            os.makedirs(os.path.dirname(log_file), exist_ok=True)

            with open(log_file, 'a') as f:
                f.write(f"\n{'=' * 80}\n")
                f.write(f"Analysis at {datetime.now().isoformat()}\n")
                f.write(f"{'-' * 80}\n")
                f.write(json.dumps(analysis, indent=2))
                f.write(f"\n{'=' * 80}\n")

        except Exception as e:
            self.logger.error(f"Error logging Claude analysis: {e}")

    def should_execute_recommendation(self, recommendation: Dict) -> bool:
        """
        Determine if recommendation should be auto-executed

        Args:
            recommendation: Recommendation from Claude

        Returns:
            True if should execute
        """
        mode = self.config.get("claude_analysis_mode", "advisory")

        if mode == "advisory":
            # Never auto-execute in advisory mode
            return False

        elif mode == "semi_autonomous":
            # Execute only high-confidence trades
            confidence_threshold = self.config.get("claude_confidence_threshold", 80)
            conviction = recommendation.get("conviction", 0)

            return conviction >= confidence_threshold

        elif mode == "autonomous":
            # Execute all recommendations
            return True

        return False

    def format_analysis_for_display(self, analysis: Dict) -> str:
        """
        Format analysis for human-readable display

        Args:
            analysis: Analysis dictionary

        Returns:
            Formatted string
        """
        if not analysis:
            return "No analysis available"

        output = []
        output.append("=" * 80)
        output.append("CLAUDE AI MARKET ANALYSIS")
        output.append("=" * 80)

        # Market Assessment
        if "market_assessment" in analysis:
            assessment = analysis["market_assessment"]
            output.append("\nMARKET ASSESSMENT:")
            output.append(f"  Regime: {assessment.get('regime', 'N/A').upper()}")
            output.append(f"  Confidence: {assessment.get('confidence', 0)}%")
            output.append(f"  Risk Level: {assessment.get('risk_level', 'N/A').upper()}")

            if "key_factors" in assessment:
                output.append("  Key Factors:")
                for factor in assessment["key_factors"]:
                    output.append(f"    - {factor}")

        # Recommendations
        if "recommended_actions" in analysis:
            output.append("\nRECOMMENDATIONS:")
            for i, rec in enumerate(analysis["recommended_actions"], 1):
                output.append(f"\n  {i}. {rec.get('action', '').upper()} {rec.get('coin', '')}")
                output.append(f"     Conviction: {rec.get('conviction', 0)}%")
                output.append(f"     Reasoning: {rec.get('reasoning', 'N/A')}")
                output.append(f"     Entry: ${rec.get('target_entry', 0):,.2f}")
                output.append(f"     Stop Loss: ${rec.get('stop_loss', 0):,.2f}")
                output.append(f"     Take Profit: ${rec.get('take_profit', [0])[0]:,.2f}")

        # Risk Warnings
        if "risk_warnings" in analysis and analysis["risk_warnings"]:
            output.append("\nRISK WARNINGS:")
            for warning in analysis["risk_warnings"]:
                output.append(f"  ⚠️  {warning}")

        # Config Suggestions
        if "config_suggestions" in analysis and analysis["config_suggestions"]:
            output.append("\nCONFIG SUGGESTIONS:")
            for suggestion in analysis["config_suggestions"]:
                output.append(f"  - {suggestion.get('parameter')}: {suggestion.get('current_value')} → {suggestion.get('suggested_value')}")
                output.append(f"    Reason: {suggestion.get('reasoning')}")

        output.append("\n" + "=" * 80)

        return "\n".join(output)

    def recommend_screener_mode(self, market_data: Dict) -> str:
        """
        Analyze market conditions and recommend best screener mode

        Args:
            market_data: Dictionary with BTC price data, fear/greed, etc.

        Returns:
            Recommended screener mode string
        """
        try:
            # Get BTC as market benchmark
            btc_data = market_data.get('BTC-USD', {})

            # Price changes
            change_24h = btc_data.get('price_change_24h', 0)
            change_7d = btc_data.get('price_change_7d', 0)
            change_30d = btc_data.get('price_change_30d', 0)

            # Volume analysis
            volume_24h = btc_data.get('volume_24h', 0)

            # Fear & Greed
            fear_greed = market_data.get('fear_greed_index', {})
            fg_value = fear_greed.get('value', 50)

            # Decision logic

            # Strong bull market: sustained gains + high fear/greed
            if change_7d > 10 and change_30d > 15 and fg_value > 60:
                self.logger.info("Market regime: STRONG BULL - Recommending 'breakouts'")
                return "breakouts"

            # Moderate bull: positive trend
            elif change_7d > 5 and change_30d > 8:
                self.logger.info("Market regime: BULL TREND - Recommending 'momentum'")
                return "momentum"

            # Extreme fear / oversold: dead cat bounce opportunity
            elif change_7d < -15 and fg_value < 20:
                self.logger.info("Market regime: EXTREME FEAR - Recommending 'bear_bounce'")
                return "bear_bounce"

            # Bear market: sustained downtrend
            elif change_7d < -5 and change_30d < -10:
                self.logger.info("Market regime: BEAR MARKET - Recommending 'mean_reversion'")
                return "mean_reversion"

            # High volatility sideways: choppy with big swings
            elif abs(change_7d) > 8 and abs(change_24h) > 3:
                self.logger.info("Market regime: HIGH VOLATILITY - Recommending 'scalping'")
                return "scalping"

            # Low volatility sideways: ranging market
            elif abs(change_7d) < 5 and abs(change_30d) < 8:
                self.logger.info("Market regime: SIDEWAYS/RANGING - Recommending 'range_trading'")
                return "range_trading"

            # Default: mean reversion for uncertain conditions
            else:
                self.logger.info("Market regime: UNCERTAIN - Defaulting to 'mean_reversion'")
                return "mean_reversion"

        except Exception as e:
            self.logger.error(f"Error determining screener mode: {e}")
            return "mean_reversion"  # Safe default
