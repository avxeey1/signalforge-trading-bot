"""Real-Time Risk Alert System.

Monitor for trading risks and trigger automated responses:
- Account risk warnings (approaching stop loss)
- Position heat monitoring (unrealized losses)
- Liquidity warnings (low volume, slippage risk)
- Volatility spikes (enter danger zones)
- Correlation breakdowns (diversification failure)
- Circuit breaker triggers (stop trading)
- Emergency liquidation (automatic risk control)
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Callable

logger = logging.getLogger("SignalForge.RiskAlerts")


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


@dataclass
class RiskAlert:
    """Risk alert notification."""
    level: AlertLevel
    trigger_type: str  # e.g., "DRAWDOWN", "LIQUIDITY", "VOLATILITY"
    message: str
    position: Optional[dict] = None
    recommended_action: str = ""
    timestamp: datetime = None


class RiskAlertSystem:
    """Real-time risk monitoring and alerting."""

    def __init__(self):
        self.alert_callbacks: list[Callable] = []  # Functions to call on alert
        self.risk_thresholds = {
            "max_account_loss": -0.20,  # Stop all trading at -20%
            "max_position_heat": -0.15,  # Close position at -15%
            "min_liquidity_sol": 0.1,  # Minimum liquidity warning
            "max_volatility_spike": 0.50,  # Vol increase >50%
            "correlation_breakdown": 0.3,  # Correlation drops >30%
            "circuit_breaker_loss": -0.10,  # Pause trading at -10%
        }

    def register_alert_callback(self, callback: Callable) -> None:
        """Register a callback for alerts."""
        self.alert_callbacks.append(callback)

    def monitor_position_heat(
        self,
        position: dict,
        current_price: float,
    ) -> Optional[RiskAlert]:
        """Monitor unrealized losses on open position.

        Args:
            position: Position dict with entry_price, size, etc.
            current_price: Current market price

        Returns:
            RiskAlert if threshold breached
        """
        try:
            entry_price = position.get("entry_price", 0)
            position_size = position.get("size", 0)
            if entry_price <= 0 or position_size <= 0:
                return None

            unrealized_pnl = (current_price - entry_price) / entry_price

            if unrealized_pnl < self.risk_thresholds["max_position_heat"]:
                alert = RiskAlert(
                    level=AlertLevel.CRITICAL,
                    trigger_type="POSITION_HEAT",
                    message=f"🚩 Position heat critical: {unrealized_pnl:.2%} loss",
                    position=position,
                    recommended_action="Consider closing position",
                    timestamp=datetime.now(),
                )
                self._trigger_alert(alert)
                return alert
        except Exception as e:
            logger.error(f"Error monitoring position heat: {e}")

        return None

    def monitor_account_drawdown(
        self,
        current_equity: float,
        peak_equity: float,
    ) -> Optional[RiskAlert]:
        """Monitor account-level drawdown.

        Args:
            current_equity: Current account equity
            peak_equity: Highest equity reached

        Returns:
            RiskAlert if threshold breached
        """
        try:
            if peak_equity <= 0:
                return None

            drawdown = (current_equity - peak_equity) / peak_equity

            if drawdown < self.risk_thresholds["max_account_loss"]:
                alert = RiskAlert(
                    level=AlertLevel.EMERGENCY,
                    trigger_type="ACCOUNT_DRAWDOWN",
                    message=f"🚨 EMERGENCY: Account drawdown {drawdown:.2%}",
                    recommended_action="LIQUIDATE ALL POSITIONS IMMEDIATELY",
                    timestamp=datetime.now(),
                )
                self._trigger_alert(alert)
                return alert
            elif drawdown < self.risk_thresholds["circuit_breaker_loss"]:
                alert = RiskAlert(
                    level=AlertLevel.CRITICAL,
                    trigger_type="CIRCUIT_BREAKER",
                    message=f"🚩 Circuit breaker: Account drawdown {drawdown:.2%}",
                    recommended_action="Pause new trades, reduce position size",
                    timestamp=datetime.now(),
                )
                self._trigger_alert(alert)
                return alert
        except Exception as e:
            logger.error(f"Error monitoring drawdown: {e}")

        return None

    def monitor_liquidity(
        self,
        token_liquidity: float,
        position_size_sol: float,
    ) -> Optional[RiskAlert]:
        """Monitor liquidity risk for position.

        Args:
            token_liquidity: Token liquidity in SOL
            position_size_sol: Position size in SOL

        Returns:
            RiskAlert if threshold breached
        """
        try:
            liquidity_ratio = position_size_sol / token_liquidity if token_liquidity > 0 else float('inf')

            if token_liquidity < self.risk_thresholds["min_liquidity_sol"]:
                alert = RiskAlert(
                    level=AlertLevel.WARNING,
                    trigger_type="LIQUIDITY_WARNING",
                    message=f"⚠️ Low liquidity: {token_liquidity:.4f} SOL",
                    recommended_action="Risk of high slippage on exit. Reduce position or exit now.",
                    timestamp=datetime.now(),
                )
                self._trigger_alert(alert)
                return alert

            if liquidity_ratio > 0.5:
                alert = RiskAlert(
                    level=AlertLevel.WARNING,
                    trigger_type="LIQUIDITY_CONCENTRATION",
                    message=f"⚠️ Position {liquidity_ratio:.0%} of liquidity",
                    recommended_action="Position too large relative to liquidity. Scale down.",
                    timestamp=datetime.now(),
                )
                self._trigger_alert(alert)
                return alert
        except Exception as e:
            logger.error(f"Error monitoring liquidity: {e}")

        return None

    def monitor_volatility_spike(
        self,
        current_volatility: float,
        normal_volatility: float,
    ) -> Optional[RiskAlert]:
        """Monitor for volatility spikes.

        Args:
            current_volatility: Current realized volatility
            normal_volatility: Historical normal volatility

        Returns:
            RiskAlert if spike detected
        """
        try:
            if normal_volatility <= 0:
                return None

            vol_spike = (current_volatility - normal_volatility) / normal_volatility

            if vol_spike > self.risk_thresholds["max_volatility_spike"]:
                alert = RiskAlert(
                    level=AlertLevel.CRITICAL,
                    trigger_type="VOLATILITY_SPIKE",
                    message=f"🚩 Volatility spike: {vol_spike:.0%} above normal",
                    recommended_action="Reduce position size, tighten stops",
                    timestamp=datetime.now(),
                )
                self._trigger_alert(alert)
                return alert
        except Exception as e:
            logger.error(f"Error monitoring volatility: {e}")

        return None

    def _trigger_alert(self, alert: RiskAlert) -> None:
        """Execute all registered alert callbacks."""
        logger.warning(f"[{alert.level.value}] {alert.message}")
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Error executing alert callback: {e}")
