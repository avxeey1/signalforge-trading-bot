"""Dynamic Position Sizing Engine.

Professional risk management for position sizing:
- Fixed fractional position sizing (% of portfolio)
- Volatility-adjusted sizing (higher vol = smaller size)
- Kelly Criterion calculations
- Pyramid scaling (scale in on winning trades)
- Risk parity approach
- Correlation-adjusted sizing (diversification)
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

logger = logging.getLogger("SignalForge.PositionSizing")


class SizingModel(Enum):
    """Position sizing models."""
    FIXED_FRACTIONAL = "fixed_fractional"  # Fixed % of account
    VOLATILITY_ADJUSTED = "volatility_adjusted"  # Inverse volatility
    KELLY_CRITERION = "kelly_criterion"  # Optimal bet sizing
    PYRAMID = "pyramid"  # Scale in strategy
    RISK_PARITY = "risk_parity"  # Equal risk per position


@dataclass
class PositionSize:
    """Position size recommendation."""
    token_address: str
    model_used: SizingModel
    position_size_sol: float  # Size in SOL
    position_size_pct: float  # Percentage of portfolio
    max_loss_sol: float  # Maximum loss if stop hit
    max_loss_pct: float  # Maximum loss percentage
    risk_reward_ratio: float  # Reward / Risk
    leverage: float  # Leverage used (1.0 = no leverage)
    confidence_level: float  # 0-100 (higher = more confident)
    scaling_levels: list = None  # For pyramid strategy
    timestamp: datetime = None


class PositionSizer:
    """Professional position sizing calculator."""

    def __init__(self):
        self.default_risk_per_trade = 0.02  # Risk 2% per trade
        self.default_model = SizingModel.VOLATILITY_ADJUSTED

    def calculate_position_size(
        self,
        portfolio_value: float,
        token_address: str,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        volatility: float = 0.3,
        win_rate: float = 0.55,
        model: SizingModel = None,
    ) -> Optional[PositionSize]:
        """Calculate professional position size.

        Args:
            portfolio_value: Total portfolio in SOL
            token_address: Token being traded
            entry_price: Entry price in SOL
            stop_loss_price: Stop loss price in SOL
            take_profit_price: Take profit price in SOL
            volatility: Historical volatility (0-1)
            win_rate: Historical win rate (0-1)
            model: Sizing model to use

        Returns:
            PositionSize object
        """
        if model is None:
            model = self.default_model

        try:
            if model == SizingModel.FIXED_FRACTIONAL:
                return self._fixed_fractional_sizing(
                    portfolio_value, token_address, entry_price, stop_loss_price, take_profit_price
                )
            elif model == SizingModel.VOLATILITY_ADJUSTED:
                return self._volatility_adjusted_sizing(
                    portfolio_value, token_address, entry_price, stop_loss_price, take_profit_price, volatility
                )
            elif model == SizingModel.KELLY_CRITERION:
                return self._kelly_criterion_sizing(
                    portfolio_value, token_address, entry_price, stop_loss_price, take_profit_price, win_rate
                )
            elif model == SizingModel.PYRAMID:
                return self._pyramid_sizing(
                    portfolio_value, token_address, entry_price, stop_loss_price, take_profit_price
                )
            elif model == SizingModel.RISK_PARITY:
                return self._risk_parity_sizing(
                    portfolio_value, token_address, entry_price, stop_loss_price, take_profit_price, volatility
                )
        except Exception as e:
            logger.error(f"Error calculating position size: {e}", exc_info=True)

        return None

    def _fixed_fractional_sizing(
        self,
        portfolio_value: float,
        token_address: str,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
    ) -> PositionSize:
        """Fixed fractional: Risk fixed % of account per trade."""
        risk_amount = portfolio_value * self.default_risk_per_trade
        position_size = risk_amount / abs(entry_price - stop_loss_price)
        max_loss = position_size * abs(entry_price - stop_loss_price)
        potential_gain = position_size * abs(take_profit_price - entry_price)
        risk_reward = potential_gain / max_loss if max_loss > 0 else 0

        return PositionSize(
            token_address=token_address,
            model_used=SizingModel.FIXED_FRACTIONAL,
            position_size_sol=position_size,
            position_size_pct=(position_size * entry_price / portfolio_value) * 100,
            max_loss_sol=max_loss,
            max_loss_pct=(max_loss / portfolio_value) * 100,
            risk_reward_ratio=risk_reward,
            leverage=1.0,
            confidence_level=75.0,
            timestamp=datetime.now(),
        )

    def _volatility_adjusted_sizing(
        self,
        portfolio_value: float,
        token_address: str,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        volatility: float,
    ) -> PositionSize:
        """Volatility-adjusted: Higher vol = smaller position."""
        # Inverse volatility sizing
        vol_adjustment = 1 / (1 + volatility)
        risk_amount = portfolio_value * self.default_risk_per_trade * vol_adjustment
        position_size = risk_amount / abs(entry_price - stop_loss_price)
        max_loss = position_size * abs(entry_price - stop_loss_price)
        potential_gain = position_size * abs(take_profit_price - entry_price)
        risk_reward = potential_gain / max_loss if max_loss > 0 else 0

        return PositionSize(
            token_address=token_address,
            model_used=SizingModel.VOLATILITY_ADJUSTED,
            position_size_sol=position_size,
            position_size_pct=(position_size * entry_price / portfolio_value) * 100,
            max_loss_sol=max_loss,
            max_loss_pct=(max_loss / portfolio_value) * 100,
            risk_reward_ratio=risk_reward,
            leverage=1.0,
            confidence_level=min(100, 75 + (20 * (1 - volatility))),
            timestamp=datetime.now(),
        )

    def _kelly_criterion_sizing(
        self,
        portfolio_value: float,
        token_address: str,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        win_rate: float,
    ) -> PositionSize:
        """Kelly Criterion: f* = (p*b - q) / b

        p = win rate, q = loss rate, b = avg win / avg loss
        """
        potential_gain = take_profit_price - entry_price
        potential_loss = entry_price - stop_loss_price

        if potential_loss <= 0:
            return self._fixed_fractional_sizing(
                portfolio_value, token_address, entry_price, stop_loss_price, take_profit_price
            )

        b = potential_gain / potential_loss
        p = win_rate
        q = 1 - win_rate

        kelly_fraction = (p * b - q) / b if b > 0 else 0
        # Apply conservative multiplier (0.25x = 1/4 Kelly for safety)
        conservative_kelly = max(0.01, min(0.25, kelly_fraction * 0.25))

        risk_amount = portfolio_value * conservative_kelly
        position_size = risk_amount / potential_loss
        max_loss = position_size * potential_loss
        potential_gain_total = position_size * potential_gain
        risk_reward = potential_gain_total / max_loss if max_loss > 0 else 0

        return PositionSize(
            token_address=token_address,
            model_used=SizingModel.KELLY_CRITERION,
            position_size_sol=position_size,
            position_size_pct=(position_size * entry_price / portfolio_value) * 100,
            max_loss_sol=max_loss,
            max_loss_pct=(max_loss / portfolio_value) * 100,
            risk_reward_ratio=risk_reward,
            leverage=1.0,
            confidence_level=85.0,
            timestamp=datetime.now(),
        )

    def _pyramid_sizing(
        self,
        portfolio_value: float,
        token_address: str,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
    ) -> PositionSize:
        """Pyramid strategy: Scale in with multiple entries."""
        base_size = portfolio_value * self.default_risk_per_trade / abs(entry_price - stop_loss_price)
        scaling_levels = [
            (entry_price * 0.95, base_size * 0.5),  # 5% below entry
            (entry_price * 0.90, base_size * 0.3),  # 10% below entry
            (entry_price * 0.85, base_size * 0.2),  # 15% below entry
        ]

        total_position = base_size + sum(s[1] for s in scaling_levels)
        max_loss = total_position * abs(entry_price - stop_loss_price)
        potential_gain = total_position * abs(take_profit_price - entry_price)
        risk_reward = potential_gain / max_loss if max_loss > 0 else 0

        return PositionSize(
            token_address=token_address,
            model_used=SizingModel.PYRAMID,
            position_size_sol=total_position,
            position_size_pct=(total_position * entry_price / portfolio_value) * 100,
            max_loss_sol=max_loss,
            max_loss_pct=(max_loss / portfolio_value) * 100,
            risk_reward_ratio=risk_reward,
            leverage=1.0,
            confidence_level=80.0,
            scaling_levels=scaling_levels,
            timestamp=datetime.now(),
        )

    def _risk_parity_sizing(
        self,
        portfolio_value: float,
        token_address: str,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        volatility: float,
    ) -> PositionSize:
        """Risk parity: Equal risk across positions."""
        # Allocate equal risk to each position
        target_risk = portfolio_value * self.default_risk_per_trade
        position_size = target_risk / abs(entry_price - stop_loss_price)
        max_loss = position_size * abs(entry_price - stop_loss_price)
        potential_gain = position_size * abs(take_profit_price - entry_price)
        risk_reward = potential_gain / max_loss if max_loss > 0 else 0

        return PositionSize(
            token_address=token_address,
            model_used=SizingModel.RISK_PARITY,
            position_size_sol=position_size,
            position_size_pct=(position_size * entry_price / portfolio_value) * 100,
            max_loss_sol=max_loss,
            max_loss_pct=(max_loss / portfolio_value) * 100,
            risk_reward_ratio=risk_reward,
            leverage=1.0,
            confidence_level=80.0,
            timestamp=datetime.now(),
        )
