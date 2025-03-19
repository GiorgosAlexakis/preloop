"""
Tracker abstraction layer for SpaceSync.
"""

from .base import BaseTracker
from .factory import TrackerFactory

__all__ = ["BaseTracker", "TrackerFactory"]
