"""Market Sentiment Analysis Engine.

Real-time sentiment tracking and correlation analysis:
- Social media sentiment (Twitter, Reddit volume)
- On-chain metrics (whale movements, exchange flows)
- Volume profile analysis
- Fear & Greed Index tracking
- Liquidity flow analysis
- Market structure (support/resistance, trend detection)
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
import requests

logger = logging.getLogger("SignalForge.Sentiment")


class SentimentLevel(Enum):
    """Market sentiment levels."""
    EXTREME_FEAR = "Extreme Fear"
    FEAR = "Fear"
    NEUTRAL = "Neutral"
    GREED = "Greed"
    EXTREME_GREED = "Extreme Greed"


@dataclass
class SentimentMetrics:
    """Sentiment analysis metrics."""
    fear_greed_index: float  # 0-100 (0=fear, 100=greed)
    sentiment_level: SentimentLevel
    social_sentiment: float  # Twitter/Reddit sentiment (-1 to +1)
    volume_trend: float  # Volume change % (last 24h vs avg)
    whale_activity: float  # Large transaction activity score
    exchange_flow: float  # Money flowing to/from exchanges
    volatility_regime: str  # LOW, MEDIUM, HIGH, EXTREME
    trend_direction: str  # UPTREND, DOWNTREND, RANGING
    liquidity_score: float  # 0-100 (higher = better liquidity)
    market_cap_rank_change: int  # Movement in market cap rankings
    timestamp: datetime = None


class MarketSentiment:
    """Market sentiment analysis engine."""

    def __init__(self):
        self.session = requests.Session()
        self.fear_greed_url = "https://api.alternative.me/fng/"
        self.coingecko_url = "https://api.coingecko.com/api/v3"

    async def analyze_market_sentiment(
        self,
        token_address: str,
        timeframe: str = "24h"
    ) -> Optional[SentimentMetrics]:
        """Analyze comprehensive market sentiment.

        Args:
            token_address: Token to analyze
            timeframe: Analysis timeframe (1h, 4h, 24h, 7d)

        Returns:
            SentimentMetrics object
        """
        try:
            # Get Fear & Greed Index
            fg_index = await self._get_fear_greed_index()

            # Get social sentiment
            social_sentiment = await self._get_social_sentiment(token_address)

            # Get volume trends
            volume_trend = await self._get_volume_trend(token_address, timeframe)

            # Get whale activity
            whale_activity = await self._get_whale_activity(token_address)

            # Get exchange flows
            exchange_flow = await self._get_exchange_flow(token_address)

            # Analyze volatility
            volatility = await self._analyze_volatility(token_address, timeframe)

            # Detect trend
            trend = await self._detect_trend(token_address, timeframe)

            # Calculate composite sentiment level
            sentiment_level = self._calculate_sentiment_level(fg_index)

            return SentimentMetrics(
                fear_greed_index=fg_index,
                sentiment_level=sentiment_level,
                social_sentiment=social_sentiment,
                volume_trend=volume_trend,
                whale_activity=whale_activity,
                exchange_flow=exchange_flow,
                volatility_regime=volatility,
                trend_direction=trend,
                liquidity_score=await self._get_liquidity_score(token_address),
                market_cap_rank_change=0,
                timestamp=datetime.now(),
            )
        except Exception as e:
            logger.error(f"Error analyzing sentiment: {e}", exc_info=True)
            return None

    async def _get_fear_greed_index(self) -> float:
        """Fetch Fear & Greed Index from alternative.me."""
        try:
            resp = self.session.get(self.fear_greed_url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return float(data["data"][0]["value"])
        except Exception as e:
            logger.warning(f"Error fetching Fear & Greed: {e}")
        return 50.0  # Default neutral

    async def _get_social_sentiment(self, token_address: str) -> float:
        """Analyze social media sentiment.

        Returns:
            float: -1.0 (very negative) to +1.0 (very positive)
        """
        # Placeholder: In production, use social media APIs
        # (Twitter API, Reddit API, LunarCrush, etc.)
        return 0.0

    async def _get_volume_trend(self, token_address: str, timeframe: str) -> float:
        """Calculate volume trend percentage."""
        # Placeholder: Connect to DEX data
        return 0.0

    async def _get_whale_activity(self, token_address: str) -> float:
        """Track whale (large transaction) activity.

        Returns:
            float: 0-100 (higher = more whale activity)
        """
        # Placeholder: Connect to on-chain analytics
        return 0.0

    async def _get_exchange_flow(self, token_address: str) -> float:
        """Track inflow/outflow to exchanges.

        Positive = inflow (selling pressure)
        Negative = outflow (buying pressure)
        """
        # Placeholder: Connect to exchange flow APIs
        return 0.0

    async def _analyze_volatility(self, token_address: str, timeframe: str) -> str:
        """Analyze volatility regime.

        Returns:
            str: LOW, MEDIUM, HIGH, or EXTREME
        """
        # Placeholder: Calculate from price data
        return "MEDIUM"

    async def _detect_trend(self, token_address: str, timeframe: str) -> str:
        """Detect price trend using moving averages.

        Returns:
            str: UPTREND, DOWNTREND, or RANGING
        """
        # Placeholder: Connect to OHLCV data
        return "RANGING"

    async def _get_liquidity_score(self, token_address: str) -> float:
        """Calculate liquidity score (0-100)."""
        # Placeholder
        return 50.0

    def _calculate_sentiment_level(self, fg_index: float) -> SentimentLevel:
        """Convert Fear & Greed index to sentiment level."""
        if fg_index < 25:
            return SentimentLevel.EXTREME_FEAR
        elif fg_index < 45:
            return SentimentLevel.FEAR
        elif fg_index < 55:
            return SentimentLevel.NEUTRAL
        elif fg_index < 75:
            return SentimentLevel.GREED
        else:
            return SentimentLevel.EXTREME_GREED

    def generate_sentiment_report(self, metrics: SentimentMetrics) -> str:
        """Generate sentiment analysis report."""
        if not metrics:
            return "No sentiment data available."

        report = (
            f"\n📈 **Market Sentiment Analysis**\n\n"
            f"**Fear & Greed Index: {metrics.fear_greed_index:.0f}/100**\n"
            f"Sentiment: {metrics.sentiment_level.value}\n\n"
            f"**Metrics:**\n"
            f"Social Sentiment: {metrics.social_sentiment:.2f}\n"
            f"Volume Trend: {metrics.volume_trend:+.2f}%\n"
            f"Whale Activity: {metrics.whale_activity:.0f}/100\n"
            f"Exchange Flow: {metrics.exchange_flow:+.2f}\n"
            f"Liquidity Score: {metrics.liquidity_score:.0f}/100\n\n"
            f"**Market Structure:**\n"
            f"Volatility: {metrics.volatility_regime}\n"
            f"Trend: {metrics.trend_direction}\n"
        )
        return report
