from __future__ import annotations
import datetime as dt
import random
from dataclasses import dataclass
from typing import List, Tuple, Optional

import requests
from bs4 import BeautifulSoup

SVG_URL = "https://github.com/users/{username}/contributions?to={to}"

@dataclass
class DayContribution:
    date: dt.date
    count: int

class ContributionsClient:
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def fetch_year_svg(self, username: str, to: Optional[dt.date] = None) -> str:
        if to is None:
            to = dt.date.today()
        url = SVG_URL.format(username=username, to=to.isoformat())
        r = requests.get(url, timeout=self.timeout, headers={
            "User-Agent": "Contribution-Graph-Pop-Quiz/1.0"
        })
        r.raise_for_status()
        return r.text

    def parse_svg(self, svg_text: str) -> List[DayContribution]:
        soup = BeautifulSoup(svg_text, "lxml")
        rects = soup.find_all("rect", {"data-date": True, "data-count": True})
        results: List[DayContribution] = []
        for rect in rects:
            date_str = rect.get("data-date")
            count_str = rect.get("data-count")
            try:
                d = dt.date.fromisoformat(date_str)
                c = int(count_str)
                results.append(DayContribution(date=d, count=c))
            except Exception:
                # Skip malformed nodes
                continue
        results.sort(key=lambda x: x.date)
        return results

    def get_contributions(self, username: str, days: int = 365) -> List[DayContribution]:
        svg = self.fetch_year_svg(username=username)
        all_days = self.parse_svg(svg)
        if not all_days:
            return []
        # Keep only the last `days` entries
        tail = all_days[-days:]
        return tail

def generate_mcq_for_date(contribs: List[DayContribution], pick_date: dt.date) -> Tuple[str, List[int], int]:
    """Return (question, options, correct_index)."""
    # Find the contribution for pick_date
    day_map = {d.date: d.count for d in contribs}
    correct = day_map.get(pick_date, 0)

    # Generate 3 distractors around the correct number; ensure uniqueness and >= 0
    offsets = set()
    rnd = random.Random(pick_date.toordinal())
    while len(offsets) < 3:
        delta = rnd.choice([1, 2, 3, 4, 5, 7, 10, 12, 15, 20])
        sign = rnd.choice([-1, 1])
        val = max(0, correct + sign * delta)
        if val != correct:
            offsets.add(val)
    options = list(offsets) + [correct]
    rnd.shuffle(options)
    correct_index = options.index(correct)

    q = f"How many contributions did you make on {pick_date.isoformat()}?"
    return q, options, correct_index

def pick_random_quizable_date(contribs: List[DayContribution], lookback_days: int = 120) -> dt.date:
    if not contribs:
        # default to yesterday
        return dt.date.today() - dt.timedelta(days=1)
    end = contribs[-1].date
    start = max(contribs[0].date, end - dt.timedelta(days=lookback_days))
    if start > end:
        start = contribs[0].date
    rng = random.Random((start.toordinal(), end.toordinal()))
    days_range = (end - start).days + 1
    return start + dt.timedelta(days=rng.randrange(days_range))
