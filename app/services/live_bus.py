import threading


_condition = threading.Condition()
_version = 0


def notify_live_change() -> None:
    global _version
    with _condition:
        _version += 1
        _condition.notify_all()


def wait_for_live_change(previous_version: int, timeout: float) -> int:
    with _condition:
        _condition.wait_for(lambda: _version != previous_version, timeout=timeout)
        return _version


def current_live_version() -> int:
    with _condition:
        return _version