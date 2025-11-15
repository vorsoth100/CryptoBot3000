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

    def _build_analysis_prompt(self, context: Dict) -> str:
        """Build analysis prompt from context"""

        # Convert all numpy types to native Python types for JSON serialization
        clean_context = convert_numpy_types(context)

        prompt = f"""You are an expert cryptocurrency trader analyzing market conditions for a bot with ${self.config.get('initial_capital', 600)} capital trading on Coinbase Advanced Trade.

**CRITICAL CONSTRAINTS:**
- Capital: ${self.config.get('initial_capital', 600)} USD
- Fees: {self.config.get('coinbase_maker_fee', 0.005) * 100}% maker, {self.config.get('coinbase_taker_fee', 0.02) * 100}% taker
- Minimum profit needed: 8% to justify trade after fees
- Maximum {self.config.get('max_positions', 3)} positions
- Stop loss: {self.config.get('stop_loss_pct', 0.06) * 100}% per position
- Maximum drawdown: {self.config.get('max_drawdown_pct', 0.20) * 100}%
- Risk tolerance: {self.config.get('claude_risk_tolerance', 'conservative')}

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

**IMPORTANT:**
- With ${self.config.get('initial_capital', 600)}, we can't afford many trades. Only suggest HIGH CONVICTION (>{self.config.get('claude_confidence_threshold', 80)}%) setups.
- Factor in fees. An 8% move = ~6% profit after fees.
- Prefer coins with high liquidity (BTC, ETH, SOL).
- If market is uncertain, suggest HOLD.
- If current drawdown >{self.config.get('max_drawdown_pct', 0.20) * 0.75 * 100}%, be VERY conservative.

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
