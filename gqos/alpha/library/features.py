import pandas as pd
import numpy as np
from typing import Dict, List, Any
from gqos.alpha.features import IFeature, FeatureMetadata

class RollingZScoreFeature(IFeature):
    """Normalizes an unbounded feature using a rolling window Z-Score."""
    def __init__(self, feature_id: str, source_feature_id: str, window: int):
        self._feature_id = feature_id
        self._source = source_feature_id
        self._window = window
        self._metadata = FeatureMetadata(
            lookback=window, lag=0, warmup=window,
            frequency="any", version="1.0", author="GQOS"
        )
        
    @property
    def feature_id(self) -> str:
        return self._feature_id
        
    @property
    def metadata(self) -> FeatureMetadata:
        return self._metadata
        
    def dependencies(self) -> List[str]:
        return [self._source]
        
    def compute(self, data: pd.DataFrame, computed_dependencies: Dict[str, pd.Series]) -> pd.Series:
        source_series = computed_dependencies[self._source]
        roll = source_series.rolling(window=self._window)
        mean = roll.mean()
        std = roll.std()
        
        # Avoid division by zero
        std = std.replace(0.0, np.nan)
        zscore = (source_series - mean) / std
        return zscore.fillna(0.0)

class MovingAverageFeature(IFeature):
    def __init__(self, feature_id: str, window: int, ma_type: str = "SMA", column: str = "close"):
        self._feature_id = feature_id
        self._window = window
        self._type = ma_type
        self._column = column
        self._metadata = FeatureMetadata(
            lookback=window, lag=0, warmup=window,
            frequency="any", version="1.0", author="GQOS"
        )

    @property
    def feature_id(self) -> str:
        return self._feature_id
        
    @property
    def metadata(self) -> FeatureMetadata:
        return self._metadata
        
    def dependencies(self) -> List[str]:
        return []
        
    def compute(self, data: pd.DataFrame, computed_dependencies: Dict[str, pd.Series]) -> pd.Series:
        series = data[self._column]
        if self._type.upper() == "EMA":
            return series.ewm(span=self._window, adjust=False).mean()
        else:
            return series.rolling(window=self._window).mean()

class MacdFeature(IFeature):
    def __init__(self, feature_id: str, fast: int = 12, slow: int = 26, signal: int = 9, column: str = "close"):
        self._feature_id = feature_id
        self.fast = fast
        self.slow = slow
        self.signal = signal
        self._column = column
        self._metadata = FeatureMetadata(
            lookback=slow + signal, lag=0, warmup=slow + signal,
            frequency="any", version="1.0", author="GQOS"
        )
        
    @property
    def feature_id(self) -> str:
        return self._feature_id
        
    @property
    def metadata(self) -> FeatureMetadata:
        return self._metadata
        
    def dependencies(self) -> List[str]:
        return []
        
    def compute(self, data: pd.DataFrame, computed_dependencies: Dict[str, pd.Series]) -> pd.Series:
        series = data[self._column]
        fast_ema = series.ewm(span=self.fast, adjust=False).mean()
        slow_ema = series.ewm(span=self.slow, adjust=False).mean()
        macd = fast_ema - slow_ema
        signal_line = macd.ewm(span=self.signal, adjust=False).mean()
        histogram = macd - signal_line
        return histogram

class RsiFeature(IFeature):
    def __init__(self, feature_id: str, window: int = 14, column: str = "close"):
        self._feature_id = feature_id
        self._window = window
        self._column = column
        self._metadata = FeatureMetadata(
            lookback=window, lag=0, warmup=window,
            frequency="any", version="1.0", author="GQOS"
        )
        
    @property
    def feature_id(self) -> str:
        return self._feature_id
        
    @property
    def metadata(self) -> FeatureMetadata:
        return self._metadata
        
    def dependencies(self) -> List[str]:
        return []
        
    def compute(self, data: pd.DataFrame, computed_dependencies: Dict[str, pd.Series]) -> pd.Series:
        delta = data[self._column].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        
        # Standard RSI uses Wilder's Smoothing (which is an EMA with alpha = 1/window)
        avg_gain = gain.ewm(alpha=1.0/self._window, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0/self._window, adjust=False).mean()
        
        rs = avg_gain / avg_loss.replace(0.0, np.nan)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        # Handle case where avg_loss is 0
        rsi = rsi.fillna(100.0)
        return rsi

class AtrFeature(IFeature):
    def __init__(self, feature_id: str, window: int = 14):
        self._feature_id = feature_id
        self._window = window
        self._metadata = FeatureMetadata(
            lookback=window + 1, lag=0, warmup=window + 1,
            frequency="any", version="1.0", author="GQOS"
        )
        
    @property
    def feature_id(self) -> str:
        return self._feature_id
        
    @property
    def metadata(self) -> FeatureMetadata:
        return self._metadata
        
    def dependencies(self) -> List[str]:
        return []
        
    def compute(self, data: pd.DataFrame, computed_dependencies: Dict[str, pd.Series]) -> pd.Series:
        high = data["high"]
        low = data["low"]
        close_prev = data["close"].shift(1)
        
        tr1 = high - low
        tr2 = (high - close_prev).abs()
        tr3 = (low - close_prev).abs()
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        # Wilder's Smoothing
        atr = tr.ewm(alpha=1.0/self._window, adjust=False).mean()
        return atr

class BollingerBandsFeature(IFeature):
    """Returns the %B (percent B). 1.0 = upper band, 0.0 = lower band, 0.5 = middle."""
    def __init__(self, feature_id: str, window: int = 20, num_std: float = 2.0, column: str = "close"):
        self._feature_id = feature_id
        self._window = window
        self._num_std = num_std
        self._column = column
        self._metadata = FeatureMetadata(
            lookback=window, lag=0, warmup=window,
            frequency="any", version="1.0", author="GQOS"
        )
        
    @property
    def feature_id(self) -> str:
        return self._feature_id
        
    @property
    def metadata(self) -> FeatureMetadata:
        return self._metadata
        
    def dependencies(self) -> List[str]:
        return []
        
    def compute(self, data: pd.DataFrame, computed_dependencies: Dict[str, pd.Series]) -> pd.Series:
        series = data[self._column]
        roll = series.rolling(window=self._window)
        mean = roll.mean()
        std = roll.std()
        
        upper = mean + (std * self._num_std)
        lower = mean - (std * self._num_std)
        
        band_width = upper - lower
        band_width = band_width.replace(0.0, np.nan)
        
        pct_b = (series - lower) / band_width
        return pct_b.fillna(0.5)

class DonchianChannelFeature(IFeature):
    """Returns the position within the channel: 1.0 = High, 0.0 = Low."""
    def __init__(self, feature_id: str, window: int = 20):
        self._feature_id = feature_id
        self._window = window
        self._metadata = FeatureMetadata(
            lookback=window, lag=0, warmup=window,
            frequency="any", version="1.0", author="GQOS"
        )
        
    @property
    def feature_id(self) -> str:
        return self._feature_id
        
    @property
    def metadata(self) -> FeatureMetadata:
        return self._metadata
        
    def dependencies(self) -> List[str]:
        return []
        
    def compute(self, data: pd.DataFrame, computed_dependencies: Dict[str, pd.Series]) -> pd.Series:
        high_roll = data["high"].rolling(window=self._window).max()
        low_roll = data["low"].rolling(window=self._window).min()
        close = data["close"]
        
        channel_width = high_roll - low_roll
        channel_width = channel_width.replace(0.0, np.nan)
        
        pos = (close - low_roll) / channel_width
        return pos.fillna(0.5)
