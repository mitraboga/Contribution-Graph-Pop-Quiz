from __future__ import annotations
import datetime as dt
from dataclasses import dataclass
from typing import List

from contributions import (
    ContributionsClient,
    DayContribution,
    generate_mcq_for_date,
    pick_random_quizable_date,
)

@dataclass
class QuizQuestion:
    text: str
    options: List[int]
    correct_index: int
    date: dt.date

class QuizEngine:
    def __init__(self):
        self.client = ContributionsClient()

    def load_user_year(self, username: str) -> List[DayContribution]:
        return self.client.get_contributions(username=username, days=365)

    def make_question(self, username: str) -> QuizQuestion:
        contribs = self.load_user_year(username)
        chosen_date = pick_random_quizable_date(contribs, lookback_days=120)
        q, options, correct_idx = generate_mcq_for_date(contribs, chosen_date)
        return QuizQuestion(text=q, options=options, correct_index=correct_idx, date=chosen_date)
