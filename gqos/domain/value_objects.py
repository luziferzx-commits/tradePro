from dataclasses import dataclass

@dataclass(frozen=True)
class ValueObject:
    """Base class for all Value Objects."""
    pass

@dataclass(frozen=True)
class Price(ValueObject):
    value: float

    def __post_init__(self):
        if self.value <= 0:
            raise ValueError(f"Price must be strictly positive, got {self.value}")

@dataclass(frozen=True)
class Probability(ValueObject):
    value: float

    def __post_init__(self):
        if not (0.0 <= self.value <= 1.0):
            raise ValueError(f"Probability must be between 0.0 and 1.0, got {self.value}")

@dataclass(frozen=True)
class LotSize(ValueObject):
    value: float

    def __post_init__(self):
        if self.value <= 0:
            raise ValueError(f"LotSize must be strictly positive, got {self.value}")

@dataclass(frozen=True)
class Spread(ValueObject):
    value: float

    def __post_init__(self):
        if self.value < 0:
            raise ValueError(f"Spread cannot be negative, got {self.value}")

@dataclass(frozen=True)
class Symbol(ValueObject):
    value: str

    def __post_init__(self):
        if not self.value or not self.value.strip():
            raise ValueError("Symbol cannot be empty")
        # Workaround for frozen dataclass
        object.__setattr__(self, 'value', self.value.upper().strip())

@dataclass(frozen=True)
class Timeframe(ValueObject):
    value: str

    def __post_init__(self):
        valid_timeframes = {"M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN"}
        if self.value not in valid_timeframes:
            raise ValueError(f"Invalid timeframe {self.value}. Must be one of {valid_timeframes}")
