"""Framework-free request handlers. Each returns (status_code, body)."""
from .ratelimit import TokenBucket
from .shortener import InvalidURLError, create_short_link, resolve
from .store import LinkStore

store = LinkStore()
limiter = TokenBucket(capacity=10, refill_per_second=0.5)


def handle_create(user_id, payload):
    if not user_id:
        return 401, {"error": "login required"}
    if not limiter.allow(user_id):
        return 429, {"error": "too many requests, slow down"}
    url = (payload or {}).get("url", "")
    try:
        code = create_short_link(store, url, user_id)
    except InvalidURLError as exc:
        return 400, {"error": str(exc)}
    except RuntimeError:
        return 503, {"error": "try again"}
    return 201, {"code": code}


def handle_redirect(code):
    url = resolve(store, code)
    if url is None:
        return 404, {"error": "not found"}
    return 302, {"location": url}


def handle_disable(user_id, code):
    try:
        found = store.disable(code, user_id)
    except PermissionError:
        return 403, {"error": "forbidden"}
    if not found:
        return 404, {"error": "not found"}
    return 200, {"disabled": code}
