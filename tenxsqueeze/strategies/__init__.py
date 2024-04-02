"""This module contains the logic multiple strategies implemented as bt.Strategy classes. 
Each strategy is a subclass of BaseStrategy and implements its own logic for entering and exiting trades.
"""

from . import MTFB3, BaseStrategy, TenXSqueeze
from .BaseStrategy import BaseStrategy
from .MTFB3 import MTFB3
from .TenXSqueeze import TenXSqueeze
