"""Request-local accounting for deadline-bounded overload recovery."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field


@dataclass(slots=True)
class OverloadRecovery:
    account_ids: set[str] = field(default_factory=set)
    retry_requested: bool = False

    def retry(self, account_id: str) -> None:
        self.account_ids.add(account_id)
        self.retry_requested = True

    def attempts(
        self,
        limit: int,
        *,
        extra_retry_requested: Callable[[], bool] | None = None,
        reset_extra_retry: Callable[[], None] | None = None,
    ) -> Iterator[int]:
        """Yield attempts while recovery-only retries skip generic increments."""
        attempt = 0
        while attempt < limit:
            self.retry_requested = False
            if reset_extra_retry is not None:
                reset_extra_retry()
            yield attempt
            if not self.retry_requested and not (extra_retry_requested is not None and extra_retry_requested()):
                attempt += 1
