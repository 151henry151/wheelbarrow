"""
Season clock — tracks which of the 4 seasons is currently active.
One full year = 4 × 15 minutes = 60 minutes real time.
"""
import time
from server.game.constants import SEASON_DURATION_S, SEASON_NAMES


class SeasonClock:
    def __init__(self):
        self.season: int = 0          # 0=spring 1=summer 2=fall 3=winter
        self._start: float = time.monotonic()

    # ------------------------------------------------------------------ load

    def load_from_db(self, season: int, season_start_dt):
        """
        Initialise from persisted state.
        `season_start_dt` is a datetime object from MariaDB.
        """
        import datetime
        self.season = season
        if season_start_dt:
            now_utc = datetime.datetime.utcnow()
            elapsed = (now_utc - season_start_dt).total_seconds()
            self._start = time.monotonic() - max(0.0, elapsed)
        else:
            self._start = time.monotonic()

    # ------------------------------------------------------------------ tick

    def tick(self) -> bool:
        """Advance season if enough real time has passed. Returns True on change."""
        if time.monotonic() - self._start >= SEASON_DURATION_S:
            self.season = (self.season + 1) % 4
            self._start = time.monotonic()
            return True
        return False

    # ---------------------------------------------------------------- helpers

    @property
    def name(self) -> str:
        return SEASON_NAMES[self.season]

    @property
    def elapsed_s(self) -> float:
        return time.monotonic() - self._start

    @property
    def remaining_s(self) -> float:
        return max(0.0, SEASON_DURATION_S - self.elapsed_s)

    def wire(self) -> dict:
        return {
            "season":      self.season,
            "name":        self.name,
            "remaining_s": int(self.remaining_s),
        }
