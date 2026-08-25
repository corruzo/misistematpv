from collections import OrderedDict, deque
from threading import Lock
from time import monotonic


_auth_attempts = OrderedDict()
_ip_attempts = OrderedDict()
_rate_limit_lock = Lock()
AUTH_RATE_WINDOW_SECONDS = 60
AUTH_RATE_LIMIT = 5
AUTH_IP_RATE_LIMIT = 30
RATE_LIMIT_MAX_KEYS = 4096


def _prune(attempts, now):
    while attempts and now - attempts[0] >= AUTH_RATE_WINDOW_SECONDS:
        attempts.popleft()


def _get_attempts(store, key, now):
    attempts = store.get(key)
    if attempts is None:
        attempts = deque()
        store[key] = attempts
    else:
        store.move_to_end(key)
    _prune(attempts, now)
    return attempts


def _evict_excess_keys(store):
    while len(store) > RATE_LIMIT_MAX_KEYS:
        store.popitem(last=False)


def is_rate_limited(scope: str, client_host: str, username: str = '') -> bool:
    now = monotonic()
    normalized_username = username.strip().lower() or '<anonymous>'
    key = f'{scope}:{client_host}:{normalized_username}'
    ip_key = f'{scope}:{client_host}'
    with _rate_limit_lock:
        ip_attempts = _get_attempts(_ip_attempts, ip_key, now)
        if len(ip_attempts) >= AUTH_IP_RATE_LIMIT:
            return True
        attempts = _get_attempts(_auth_attempts, key, now)
        if len(attempts) >= AUTH_RATE_LIMIT:
            return True
        ip_attempts.append(now)
        attempts.append(now)
        _evict_excess_keys(_auth_attempts)
        _evict_excess_keys(_ip_attempts)
        return False