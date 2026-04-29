from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class P1P2Stats(Base):
    """
    One row per completed parent candle.

    P1 = the first significant extreme (high or low) that forms within the candle period,
         identified using sub-candle data (e.g. hourly candles inside a weekly candle).
    P2 = the second extreme, in the opposite direction, that forms after P1.
    Flip = P1 gets invalidated (a new extreme in the same direction forms after P1).

    All _pct fields are expressed as a percentage of the candle's open price.
    All _time_pct fields are 0–100, representing how far through the candle period
    the event occurred (0 = candle open, 100 = candle close).
    """

    __tablename__ = "p1p2_stats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    candle_open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Parent candle OHLC (denormalized — avoids joins in stat queries)
    open_price: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)

    # ── P1: first extreme to form ──────────────────────────────────────────────
    p1_side: Mapped[str | None] = mapped_column(String(5), nullable=True)
    # "low" | "high" — which extreme printed first

    p1_price: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    p1_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    p1_dist_pct: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    # (p1_price - open) / open * 100  →  negative when p1_side = "low"

    p1_time_pct: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    # % of candle period elapsed when original P1 formed

    # ── Flip tracking ──────────────────────────────────────────────────────────
    p1_flip_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 0 = no flip; 1 = one reset; 2 = double flip, etc.

    p1_flip_occurred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Final P1: last confirmed P1 after all flips ────────────────────────────
    # Equals original P1 when p1_flip_count = 0.
    final_p1_price: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    final_p1_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    final_p1_dist_pct: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    final_p1_time_pct: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)

    # ── P2: second extreme, opposite direction from final P1 ───────────────────
    p2_price: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    p2_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    p2_dist_pct: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    p2_time_pct: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)

    # ── Derived convenience flags (used heavily in stat filters) ───────────────
    is_bullish: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # True when close > open

    low_held: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # True when final_p1_side = "low" AND p1_flip_count = 0
    # Used to filter "Long Targets if Current Low Holds"

    high_held: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # True when final_p1_side = "high" AND p1_flip_count = 0

    # ── Data quality ───────────────────────────────────────────────────────────
    sub_candle_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Number of sub-candles used; NULL means this row was populated from OHLC
    # alone (no sub-candle data available — p1/p2 fields will be NULL too)

    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "candle_open_time", name="uq_p1p2_symbol_tf_time"),
        Index("ix_p1p2_symbol_tf", "symbol", "timeframe"),
        Index("ix_p1p2_symbol_tf_time", "symbol", "timeframe", "candle_open_time"),
    )
