"""Create or rotate a gate agent API key.

Run from the repository root after applying Alembic migrations:
    .venv\\Scripts\\python.exe scripts\\create_gate_agent.py --id garita-prueba --name "Garita de prueba"
"""
import argparse
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database.session import SessionLocal
from app.models.gate_agent import GateAgent
from app.services.agent_service import hash_agent_api_key


def main():
    parser = argparse.ArgumentParser(description='Registrar una garita y generar su API key')
    parser.add_argument('--id', required=True, dest='garita_id', help='Identificador estable de la garita')
    parser.add_argument('--name', required=True, dest='name', help='Nombre visible de la garita')
    parser.add_argument('--rotate', action='store_true', help='Rotar la clave si la garita ya existe')
    args = parser.parse_args()
    api_key = secrets.token_urlsafe(32)

    with SessionLocal() as db:
        agent = db.query(GateAgent).filter(GateAgent.codigo == args.garita_id).first()
        if agent and not args.rotate:
            raise SystemExit('La garita ya existe. Usa --rotate para generar una nueva clave.')
        if agent:
            agent.nombre = args.name
            agent.api_key_hash = hash_agent_api_key(api_key)
            agent.activo = True
            agent.revocado_en = None
        else:
            db.add(GateAgent(
                codigo=args.garita_id,
                nombre=args.name,
                api_key_hash=hash_agent_api_key(api_key),
                activo=True,
            ))
        db.commit()

    print(f'GARITA_ID={args.garita_id}')
    print(f'API_KEY={api_key}')
    print('Guarda esta API_KEY ahora: no se almacena en texto plano y no puede recuperarse desde la base de datos.')


if __name__ == '__main__':
    main()
