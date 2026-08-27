import logging
import argparse
import random
import threading
import uuid
from datetime import datetime, timezone

import serial

from rfid_agent.client import CentralClient, PermanentAgentError, TemporaryAgentError
from rfid_agent.config import AgentConfig, load_config
from rfid_agent.queue import ScanQueue

logger = logging.getLogger('rfid_agent')
VERSION = '1.0.0'


class RfidAgent:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.stop_event = threading.Event()
        self.reader_connected = False
        self.last_scan_at = None
        self.queue = ScanQueue(config.queue_path, config.queue_limit)
        self.client = CentralClient(config.server_url, config.api_key, config.garita_id)

    def start(self):
        threading.Thread(target=self._read_loop, name='rfid-reader', daemon=True).start()
        threading.Thread(target=self._sync_loop, name='rfid-sync', daemon=True).start()
        threading.Thread(target=self._heartbeat_loop, name='rfid-heartbeat', daemon=True).start()
        self.stop_event.wait()

    def stop(self):
        self.stop_event.set()

    def _read_loop(self):
        while not self.stop_event.is_set():
            try:
                with serial.Serial(
                    port=self.config.serial_port,
                    baudrate=self.config.baud_rate,
                    bytesize=self.config.bytesize,
                    parity=self.config.parity,
                    stopbits=self.config.stopbits,
                    timeout=self.config.timeout,
                ) as connection:
                    self.reader_connected = True
                    while not self.stop_event.is_set():
                        raw = connection.readline()
                        if not raw:
                            continue
                        card_code = raw.decode(self.config.encoding).strip()
                        if card_code:
                            timestamp = datetime.now(timezone.utc).isoformat()
                            self.last_scan_at = timestamp
                            self.queue.enqueue(card_code=card_code, operation_id=str(uuid.uuid4()), timestamp=timestamp)
            except (serial.SerialException, UnicodeDecodeError, RuntimeError) as exc:
                self.reader_connected = False
                logger.warning('Lector RFID no disponible o cola llena: %s', exc)
                self.stop_event.wait(5)

    def _sync_loop(self):
        delay = 1.0
        while not self.stop_event.is_set():
            rows = self.queue.pending()
            if not rows:
                delay = 1.0
                self.stop_event.wait(1)
                continue
            queue_id, operation_id, card_code, timestamp, _attempts = rows[0]
            try:
                self.client.send_scan(operation_id, card_code, timestamp, datetime.now(timezone.utc).isoformat(), VERSION)
                self.queue.acknowledge(queue_id)
                delay = 1.0
            except PermanentAgentError as exc:
                self.queue.reject(queue_id, operation_id, card_code, timestamp, exc.status_code, exc.reason)
                delay = 1.0
            except TemporaryAgentError as exc:
                self.queue.mark_attempt(queue_id, str(exc))
                delay = min(delay * 2, 300) * random.uniform(0.8, 1.2)
                self.stop_event.wait(delay)

    def _heartbeat_loop(self):
        while not self.stop_event.is_set():
            try:
                self.client.heartbeat(self.reader_connected, len(self.queue.pending()), self.last_scan_at, VERSION)
            except (PermanentAgentError, TemporaryAgentError) as exc:
                logger.warning('No se pudo enviar heartbeat: %s', exc)
            self.stop_event.wait(self.config.heartbeat_seconds)


def main():
    parser = argparse.ArgumentParser(description='Agente RFID independiente de MarcajeTPV')
    parser.add_argument('--config', default='.env', help='Ruta al archivo de configuración del agente')
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    config = load_config(arguments.config)
    if not all((config.serial_port, config.server_url, config.garita_id, config.api_key)):
        raise SystemExit('PUERTO_COM, URL_SERVIDOR, GARITA_ID y API_KEY son obligatorios.')
    RfidAgent(config).start()


if __name__ == '__main__':
    main()