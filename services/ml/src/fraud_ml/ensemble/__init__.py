"""Generic ensemble math retained while Sparkov Task 5 is blocked."""

TASK5_BLOCKED = (
    "Task 5 blocked: Sparkov Task 4 evidence and approved operating constraints "
    "required; no compatible frozen bundle"
)


def block_task5() -> None:
    raise SystemExit(TASK5_BLOCKED)
