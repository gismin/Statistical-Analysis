# Import all models here so Base.metadata is fully populated before create_all runs.
# Any new model file must be imported in this module.
from app.models.ohlcv import OHLCV, SessionStats  # noqa: F401
from app.models.p1p2_stats import P1P2Stats  # noqa: F401
