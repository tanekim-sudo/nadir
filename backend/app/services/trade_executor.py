"""
Trade Executor — connects to Alpaca API for execution.
PAPER TRADING MODE BY DEFAULT.
"""
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class TradeExecutor:
    def __init__(self):
        self.paper = os.getenv("ALPACA_LIVE", "false").lower() != "true"
        base_url = (
            "https://paper-api.alpaca.markets"
            if self.paper
            else "https://api.alpaca.markets"
        )

        try:
            import alpaca_trade_api as tradeapi
            self.api = tradeapi.REST(
                os.getenv("ALPACA_API_KEY", ""),
                os.getenv("ALPACA_SECRET_KEY", ""),
                base_url=base_url,
            )
            self._available = True
        except Exception as e:
            logger.warning("Alpaca API not available: %s", e)
            self.api = None
            self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def is_paper(self) -> bool:
        return self.paper

    def get_portfolio_value(self) -> float:
        if not self._available:
            return 100000.0
        account = self.api.get_account()
        return float(account.portfolio_value)

    def get_open_positions(self) -> List[Dict[str, Any]]:
        if not self._available:
            return []
        positions = self.api.list_positions()
        return [
            {
                "ticker": p.symbol,
                "shares": int(p.qty),
                "current_price": float(p.current_price),
                "entry_price": float(p.avg_entry_price),
                "market_value": float(p.market_value),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc),
                "position_pct": float(p.market_value) / self.get_portfolio_value(),
            }
            for p in positions
        ]

    def execute_entry(
        self, ticker: str, dollar_amount: float
    ) -> Tuple[Optional[Any], Optional[str]]:
        if not self._available:
            return None, "Alpaca API not available"

        try:
            quote = self.api.get_last_quote(ticker)
            mid_price = (float(quote.askprice) + float(quote.bidprice)) / 2
            shares = int(dollar_amount / mid_price)

            if shares == 0:
                return None, "Position too small for minimum share quantity"

            limit_price = round(mid_price * 1.005, 2)

            order = self.api.submit_order(
                symbol=ticker,
                qty=shares,
                side="buy",
                type="limit",
                limit_price=limit_price,
                time_in_force="day",
                client_order_id=f"nadir_{ticker}_{int(time.time())}",
            )
            return order, None

        except Exception as e:
            logger.error("Entry execution failed for %s: %s", ticker, e)
            return None, str(e)

    def execute_exit(
        self, ticker: str, shares: int, reason: str
    ) -> Tuple[Optional[Any], Optional[str]]:
        if not self._available:
            return None, "Alpaca API not available"

        try:
            order = self.api.submit_order(
                symbol=ticker,
                qty=shares,
                side="sell",
                type="market",
                time_in_force="day",
                client_order_id=f"exit_{ticker}_{int(time.time())}",
            )
            return order, None

        except Exception as e:
            logger.error("Exit execution failed for %s: %s", ticker, e)
            return None, str(e)

    def get_current_price(self, ticker: str) -> Optional[float]:
        if not self._available:
            return None
        try:
            quote = self.api.get_last_quote(ticker)
            return (float(quote.askprice) + float(quote.bidprice)) / 2
        except Exception:
            return None
