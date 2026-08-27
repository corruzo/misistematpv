"""Smoke test for a registered RFID gate agent.

Example:
    .venv\\Scripts\\python.exe scripts\\test_agent_push.py \\
    --url http://127.0.0.1:8000 --garita-id garita-prueba \
    --api-key THE_KEY --card CARD-001
"""
import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def post(url, api_key, payload):
    request = Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urlopen(request, timeout=10) as response:
            body = response.read().decode('utf-8')
            print(f'{response.status} {url}\n{body}')
            return response.status
    except HTTPError as error:
        print(f'{error.code} {url}\n{error.read().decode("utf-8", errors="replace")}')
        return error.code
    except (URLError, TimeoutError) as error:
        print(f'NETWORK ERROR {url}: {error}')
        return 599


def main():
    parser = argparse.ArgumentParser(description='Simular heartbeat y marcaje RFID')
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--garita-id', required=True)
    parser.add_argument('--api-key', required=True)
    parser.add_argument('--card', required=True, help='Codigo de tarjeta existente en empleados')
    args = parser.parse_args()
    now = datetime.now(timezone.utc).isoformat()
    heartbeat_status = post(
        f'{args.url.rstrip("/")}/api/v1/garitas/{args.garita_id}/heartbeat',
        args.api_key,
        {
            'garita_id': args.garita_id,
            'agent_version': 'smoke-test',
            'reader_connected': True,
            'queue_depth': 0,
            'last_scan_at': now,
        },
    )
    operation_id = str(uuid.uuid4())
    scan_status = post(
        f'{args.url.rstrip("/")}/api/v1/asistencia/lectura',
        args.api_key,
        {
            'garita_id': args.garita_id,
            'operation_id': operation_id,
            'codigo_tarjeta': args.card,
            'timestamp_lectura': now,
            'timestamp_envio': datetime.now(timezone.utc).isoformat(),
            'agent_version': 'smoke-test',
        },
    )
    if heartbeat_status != 200 or scan_status not in (200, 201):
        return 1
    print(f'operation_id={operation_id}')
    print('Smoke test HTTP completado. Abre /attendance/summary y verifica el evento SSE.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
