from app.core.llm.errors import BudgetExceededError

DEFAULT_RUN_CAP_USD = 0.05


class RunBudget:
    """Spend tracker for one agent run. Cost is only known after a call, so a single call can
    overshoot the cap; the next one is refused."""

    def __init__(self, run_id: str, cap_usd: float = DEFAULT_RUN_CAP_USD) -> None:
        self.run_id = run_id
        self.cap_usd = cap_usd
        self.spent_usd = 0.0

    def ensure_available(self) -> None:
        if self.spent_usd >= self.cap_usd:
            raise BudgetExceededError(
                f"run {self.run_id} spent ${self.spent_usd:.4f} of ${self.cap_usd:.4f}"
            )

    def record(self, cost_usd: float) -> None:
        self.spent_usd += cost_usd
