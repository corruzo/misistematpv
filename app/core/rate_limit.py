from collections import defaultdict, deque
from time import monotonic


_auth_attempts = defaultdict(deque)
AUTH_RATE_WINDOW_SECONDS = 60
AUTH_RATE_LIMIT = 5


def is_rate_limited(scope: str, client_host: str, username: str = '') -> bool:
    now = monotonic()
    normalized_username = username.strip().lower() or '<anonymous>'
    key = f'{scope}:{client_host}:{normalized_username}'
    attempts = _auth_attempts[key]
    while attempts and now - attempts[0] >= AUTH_RATE_WINDOW_SECONDS:
        attempts.popleft()
    if len(attempts) >= AUTH_RATE_LIMIT:
        return True
    attempts.append(now)
    return False