"""
Timing utilities.
"""

import time


class StopWatch:
    """Context manager for timing code blocks."""

    def __init__(self):
        self.elapsed_ms = 0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = int((time.perf_counter() - self._start) * 1000)
