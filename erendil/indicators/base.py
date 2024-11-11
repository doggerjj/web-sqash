import numpy as np
import polars as pl
from abc import ABC, abstractmethod
from erendil.models.data_models import MAType

class BaseIndicator(ABC):

    @abstractmethod
    def process_data(self, df: pl.DataFrame):
        pass