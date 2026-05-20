from dataclasses import dataclass


@dataclass
class CostGuard:
    max_depth: int
    max_result_bytes: int
    _calls: int = 0

    def can_call_again(self) -> bool:
        return self._calls < self.max_depth

    def note_call(self) -> None:
        self._calls += 1

    def maybe_truncate(self, payload: str) -> tuple[str, bool]:
        b = payload.encode("utf-8")
        if len(b) <= self.max_result_bytes:
            return payload, False
        return b[: self.max_result_bytes].decode("utf-8", errors="ignore"), True
