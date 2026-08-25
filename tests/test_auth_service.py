from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import MagicMock

from app.models.auth_session import AuthSession
from app.models.user import Usuario
from app.services.auth_service import (
    INITIAL_SETUP_LOCK,
    acquire_initial_setup_lock,
    authenticate_user,
    create_session,
    delete_session,
    get_user_by_token,
    hash_session_token,
    invalidate_user_sessions,
    SESSION_HOURS,
)
from app.core.security import hash_password
from app.services.user_service import set_user_status


class QueryDouble:
    def __init__(self, result):
        self.result = result

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.result


class AuthServiceTest(unittest.TestCase):
    def test_password_change_invalidates_all_user_sessions(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.delete.return_value = 3

        invalidated = invalidate_user_sessions(db, 7)

        self.assertEqual(invalidated, 3)
        db.query.return_value.filter.return_value.delete.assert_called_once_with(synchronize_session=False)

    def test_initial_setup_acquires_transactional_sql_server_lock(self):
        db = MagicMock()
        db.execute.return_value.scalar.return_value = 0

        acquire_initial_setup_lock(db)

        statement = db.execute.call_args.args[0]
        self.assertIn('sp_getapplock', statement.text)
        self.assertEqual(db.execute.call_args.args[1], {'resource': INITIAL_SETUP_LOCK})

    def test_initial_setup_rejects_failed_sql_server_lock(self):
        db = MagicMock()
        db.execute.return_value.scalar.return_value = -3

        with self.assertRaisesRegex(RuntimeError, 'bloqueo'):
            acquire_initial_setup_lock(db)

    def test_authenticate_rejects_wrong_password_and_corrupt_hash(self):
        db = MagicMock()
        user = Usuario(username='ana', activo=1, password_hash=hash_password('UnaClaveSegura123'))
        db.query.return_value = QueryDouble(user)

        self.assertIsNone(authenticate_user(db, 'ana', 'incorrecta'))
        user.password_hash = 'not-a-valid-hash'
        self.assertIsNone(authenticate_user(db, 'ana', 'UnaClaveSegura123'))

    def test_create_and_delete_session(self):
        db = MagicMock()
        token = create_session(db, 7)

        self.assertTrue(token)
        session = db.add.call_args.args[0]
        self.assertEqual(session.user_id, 7)
        self.assertEqual(session.token_hash, hash_session_token(token))
        remaining_hours = (session.expires_at - datetime.now(timezone.utc)).total_seconds() / 3600
        self.assertAlmostEqual(remaining_hours, SESSION_HOURS, delta=0.01)
        db.delete.assert_not_called()

        db.query.return_value = QueryDouble(session)
        delete_session(db, token)
        db.delete.assert_called_once_with(session)

    def test_expired_session_is_deleted_and_returns_no_user(self):
        db = MagicMock()
        session = AuthSession(
            user_id=7,
            token_hash=hash_session_token('expired'),
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db.query.return_value = QueryDouble(session)

        self.assertIsNone(get_user_by_token(db, 'expired'))
        db.delete.assert_called_once_with(session)

    def test_valid_session_returns_active_user(self):
        db = MagicMock()
        session = AuthSession(
            user_id=7,
            token_hash=hash_session_token('valid'),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        user = Usuario(id=7, activo=1, username='ana')
        db.query.side_effect = [QueryDouble(session), QueryDouble(user)]

        self.assertIs(get_user_by_token(db, 'valid'), user)
        db.delete.assert_not_called()

    def test_admin_cannot_disable_own_user(self):
        db = MagicMock()
        user = Usuario(id=1, rol='Administrador', activo=1)
        db.query.return_value.filter.return_value.first.return_value = user

        with self.assertRaisesRegex(ValueError, 'propio usuario'):
            set_user_status(db, 1, False, actor_id=1)

        db.add.assert_not_called()

    def test_last_active_admin_cannot_be_disabled(self):
        db = MagicMock()
        user = Usuario(id=1, rol='Administrador', activo=1)
        db.query.return_value.filter.return_value.first.return_value = user
        db.query.return_value.filter.return_value.count.return_value = 1

        with self.assertRaisesRegex(ValueError, 'al menos un administrador activo'):
            set_user_status(db, 1, False, actor_id=2)

        db.add.assert_not_called()


if __name__ == '__main__':
    unittest.main()
