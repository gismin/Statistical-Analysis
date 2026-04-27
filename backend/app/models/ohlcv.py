from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class OHLCV(Base):
    __tablename__ = "ohlcv"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    volume: Mapped[float] = mapped_column(Numeric(30, 8), nullable=False)

    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "open_time", name="uq_ohlcv_symbol_tf_time"),
        Index("ix_ohlcv_symbol_tf_time", "symbol", "timeframe", "open_time"),
    )


class SessionStats(Base):
    """Precomputed per-session stats used by Time and Distance features."""

    __tablename__ = "session_stats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    session_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Time feature fields
    high_time_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    low_time_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    # Distance feature fields
    range_atr_pct: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    atr14: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)

    # Outcome labels (filled after session closes)
    high_taken_out: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    low_taken_out: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "session_date", name="uq_session_stats"),
        Index("ix_session_stats_symbol_tf", "symbol", "timeframe"),
    )
