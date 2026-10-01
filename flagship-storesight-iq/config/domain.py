"""
Runtime taxonomy loader — the single source of truth for the QSR domain.

`config/domain.json` is emitted by `accelerator/generate.py` from the
human-authored `accelerator/domain.yaml`. Loading it here (stdlib json, no new
dependency) means the product taxonomy — prep subtypes, ingredient categories,
dayparts, stores, sales channels — lives in exactly ONE place that both the
FastAPI backend and the training notebooks consume. This is what prevents the
ML feature-contract drift between `services/model_serving.py` and notebooks
04/05 that had to be reconciled by hand on the prior single-customer build.

Usage:
    from config.domain import domain
    domain.prep_subtypes()            # list of subtype dicts
    domain.category_encoding()        # {"main": 1, ...}
    domain.daypart_for(hour=18)       # -> daypart dict or None
"""

import json
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

_DOMAIN_PATH = os.path.join(os.path.dirname(__file__), "domain.json")


class Domain:
    """Thin, cached accessor over config/domain.json."""

    def __init__(self, path: str = _DOMAIN_PATH):
        self._path = path
        with open(path, "r", encoding="utf-8") as f:
            self._d: Dict[str, Any] = json.load(f)

    # --- raw sections -------------------------------------------------------
    @property
    def raw(self) -> Dict[str, Any]:
        return self._d

    def prep(self) -> Dict[str, Any]:
        return self._d.get("prep", {})

    def prep_subtypes(self) -> List[Dict[str, Any]]:
        return self._d.get("prep", {}).get("subtypes", [])

    def operating_hours(self) -> Dict[str, int]:
        return self._d.get("operating_hours", {"open": 6, "close": 22})

    def dayparts(self) -> List[Dict[str, Any]]:
        return self._d.get("dayparts", [])

    def labor_dayparts(self) -> Dict[str, List[int]]:
        return self._d.get("labor_dayparts", {})

    def rush_hours(self) -> Dict[str, int]:
        return self._d.get("rush_hours", {"start": 17, "end": 20})

    def category_encoding(self) -> Dict[str, int]:
        return self._d.get("ingredient_categories", {})

    def ingredients(self) -> List[Dict[str, Any]]:
        return self._d.get("ingredients", [])

    def menu_items(self) -> List[str]:
        """Customer-facing menu/product names (for demo transactions)."""
        return self._d.get("menu_items", [])

    def sales_channels(self) -> List[Dict[str, Any]]:
        return self._d.get("sales_channels", [])

    def supplier_name(self) -> str:
        return self._d.get("supplier_name", "Distribution Center")

    def stores(self) -> List[Dict[str, Any]]:
        return self._d.get("stores", [])

    def num_stores(self) -> int:
        return len(self.stores())

    def data_generation(self) -> Dict[str, Any]:
        return self._d.get("data_generation", {"days_of_history": 365, "transactions_per_day_avg": 200})

    def genie_sample_questions(self) -> List[str]:
        return self._d.get("genie_sample_questions", [])

    # --- helpers ------------------------------------------------------------
    def subtype_by_key(self, key: str) -> Optional[Dict[str, Any]]:
        for s in self.prep_subtypes():
            if s.get("key") == key:
                return s
        return None

    def daypart_for(self, hour: int) -> Optional[Dict[str, Any]]:
        """Return the daypart whose [start, end) range contains `hour`."""
        for dp in self.dayparts():
            if dp.get("start", 0) <= hour < dp.get("end", 0):
                return dp
        return None

    def is_rush_hour(self, hour: int) -> bool:
        r = self.rush_hours()
        return r.get("start", 17) <= hour <= r.get("end", 20)

    def channel_labels(self) -> Dict[str, str]:
        return {c["key"]: c.get("label", c["key"]) for c in self.sales_channels()}


@lru_cache(maxsize=1)
def _load() -> Domain:
    return Domain()


# Singleton-style accessor
domain = _load()
