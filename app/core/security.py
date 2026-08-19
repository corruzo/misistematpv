import base64
import hashlib
import hmac
import secrets


ALGORITHM = 'scrypt'
SALT_BYTES = 16
HASH_BYTES = 32
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1


def hash_password(password: str) -> str:
    if not isinstance(password, str) or len(password) < 10:
        raise ValueError('La contraseña debe tener al menos 10 caracteres.')
    salt = secrets.token_bytes(SALT_BYTES)
    derived_key = hashlib.scrypt(
        password.encode('utf-8'),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=HASH_BYTES,
    )
    encode = lambda value: base64.urlsafe_b64encode(value).decode('ascii')
    return f'{ALGORITHM}${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${encode(salt)}${encode(derived_key)}'


def verify_password(password: str, encoded_password: str) -> bool:
    try:
        algorithm, n, r, p, encoded_salt, encoded_hash = encoded_password.split('$')
        if algorithm != ALGORITHM:
            return False
        salt = base64.urlsafe_b64decode(encoded_salt.encode('ascii'))
        expected = base64.urlsafe_b64decode(encoded_hash.encode('ascii'))
        actual = hashlib.scrypt(
            password.encode('utf-8'),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (TypeError, ValueError, UnicodeError):
        return False
