class PositionManager:
    def __init__(self):
        self.position = 0
        self.entry_price = None
        self.stoploss = None
        self.trailing_stoploss = None
    
    def reset(self):
        self.position = 0
        self.entry_price = None
        self.stoploss = None
        self.trailing_stoploss = None