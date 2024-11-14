class PositionManager:
    def __init__(self):
        self.position = 0
        self.entry_price = None
        self.entry_timestamp = None
        self.first_exit_price = None
        self.second_exit_price = None
        self.trailing_stoploss = None
        self.first_exit_timestamp = None
        self.second_exit_timestamp = None
    
    def reset(self):
        self.position = 0
        self.entry_price = None
        self.entry_timestamp = None
        self.first_exit_price = None
        self.second_exit_price = None
        self.trailing_stoploss = None
        self.first_exit_timestamp = None
        self.second_exit_timestamp = None
    