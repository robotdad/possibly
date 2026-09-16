"""Possibly's library. Importing this package never initializes intelligence."""

from .lib import Possibly
from .models import Grant, PossiblyError, Presentation

__all__ = ["Possibly", "Grant", "Presentation", "PossiblyError"]
