import json
import urllib.error
import urllib.request


class TemporaryAgentError(Exception):
    pass


class PermanentAgentError(Exception):
    def __init__(self, status_code: int, reason: str):
        self.status_code = status_code
        self.reason = reason


class CentralClient:
    def __init__(self, server_url: str, api_key: str, garita_id: str, timeout: float = 10):
        self.server_url = server_url
        self.api_key = api_key
        self.garita_id = garita_id
        self.timeout = timeout

    def _request(self, path: str, payload: dict) -> dict:
        request = urllib.request.Request(
            f'{self.server_url}{path}',
            data=json.dumps(payload).encode('utf-8'),
            headers={'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read() or b'{}')
        except urllib.error.HTTPError as exc:
            reason = exc.read().decode('utf-8', errors='replace')
            if 400 <= exc.code < 500:
                raise PermanentAgentError(exc.code, reason) from exc
            raise TemporaryAgentError(f'HTTP {exc.code}') from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise TemporaryAgentError(str(exc)) from exc

    def send_scan(self, operation_id: str, card_code: str, timestamp: str, sent_at: str, version: str | None = None) -> dict:
        return self._request('/api/v1/asistencia/lectura', {
            'garita_id': self.garita_id,
            'operation_id': operation_id,
            'codigo_tarjeta': card_code,
            'timestamp_lectura': timestamp,
            'timestamp_envio': sent_at,
            'agent_version': version,
        })

    def heartbeat(self, reader_connected: bool, queue_depth: int, last_scan_at: str | None, version: str | None = None) -> dict:
        return self._request(f'/api/v1/garitas/{self.garita_id}/heartbeat', {
            'garita_id': self.garita_id,
            'agent_version': version,
            'reader_connected': reader_connected,
            'queue_depth': queue_depth,
            'last_scan_at': last_scan_at,
        })