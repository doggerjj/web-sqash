from enum import Enum

class MAType(Enum):
    SMA = "SMA"
    EMA = "EMA"

class SmoothingType(Enum):
    RMA = "RMA"
    SMA = "SMA"
    EMA = "EMA"
    WMA = "WMA"