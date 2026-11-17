"""Create and resolve short links."""
import secrets
from urllib.parse import urlparse

from .store import LinkStore, DuplicateCodeError

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
CODE_LENGTH = 7
MAX_ATTEMPTS = 5


class InvalidURLError(ValueError):
    pass


def encode_base62(number: int) -> str:
    if number == 0:
        return ALPHABET[0]
    digits = []
    while number > 0:
        number, remainder = divmod(number, 62)
        digits.append(ALPHABET[remainder])
    return "".join(reversed(digits))


def random_code(length: int = CODE_LENGTH) -> str:
    value = secrets.randbits(length * 6)
    return encode_base62(value).rjust(length, ALPHABET[0])[:length]


def validate_url(url: str) -> str:
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise InvalidURLError("only http and https links are allowed")
    if not parsed.netloc:
        raise InvalidURLError("link has no host")
    if len(url) > 2048:
        raise InvalidURLError("link is too long")
    return url


def create_short_link(store: LinkStore, url: str, owner_id: str) -> str:
    url = validate_url(url)
    existing = store.find_by_url(url, owner_id)
    if existing:
        return existing
    for _ in range(MAX_ATTEMPTS):
        code = random_code()
        try:
            store.save(code, url, owner_id)
            return code
        except DuplicateCodeError:
            continue
    raise RuntimeError("could not generate a unique code")


def resolve(store: LinkStore, code: str):
    record = store.get(code)
    if record is None or record.disabled:
        return None
    store.increment_clicks(code)
    return record.url
