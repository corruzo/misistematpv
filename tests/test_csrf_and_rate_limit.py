import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.rate_limit import AUTH_IP_RATE_LIMIT, AUTH_RATE_LIMIT, is_rate_limited
from run import SecurityHeadersMiddleware


class CsrfAndRateLimitTest(unittest.TestCase):
    def test_disallowed_origin_is_rejected(self):
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.post('/change')
        def change():
            return {'ok': True}

        response = TestClient(app).post('/change', headers={'Origin': 'https://untrusted.example'})
        self.assertEqual(response.status_code, 403)

    def test_missing_origin_is_rejected_and_get_issues_csrf_cookie(self):
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get('/page')
        def page():
            return {'ok': True}

        @app.post('/change')
        def change():
            return {'ok': True}

        client = TestClient(app)
        page_response = client.get('/page')
        change_response = client.post('/change')

        self.assertEqual(page_response.status_code, 200)
        self.assertIn('csrftoken=', page_response.headers['set-cookie'])
        self.assertEqual(change_response.status_code, 403)

    def test_allowed_origin_is_accepted(self):
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.post('/change')
        def change():
            return {'ok': True}

        client = TestClient(app)
        page_response = client.get('/page')
        token = page_response.cookies.get('csrftoken')
        response = client.post('/change', headers={'Origin': 'http://localhost:8000', 'X-CSRFToken': token})
        self.assertEqual(response.status_code, 200)
        self.assertIn('nonce-', response.headers['content-security-policy'])

    def test_rate_limit_blocks_after_configured_attempts_per_identity(self):
        scope = '/test-rate-limit'
        for _ in range(AUTH_RATE_LIMIT):
            self.assertFalse(is_rate_limited(scope, '192.0.2.10', 'user-a'))
        self.assertTrue(is_rate_limited(scope, '192.0.2.10', 'user-a'))
        self.assertFalse(is_rate_limited(scope, '192.0.2.10', 'user-b'))

    def test_rate_limit_also_blocks_many_usernames_from_one_ip(self):
        scope = '/test-ip-rate-limit'
        for index in range(AUTH_IP_RATE_LIMIT):
            self.assertFalse(is_rate_limited(scope, '192.0.2.11', f'user-{index}'))
        self.assertTrue(is_rate_limited(scope, '192.0.2.11', 'new-user'))


if __name__ == '__main__':
    unittest.main()
