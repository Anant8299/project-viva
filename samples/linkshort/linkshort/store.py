"""In-memory storage for short links. Thread-safe enough for a single process."""
import threading
import time
from dataclasses import dataclass, field


class DuplicateCodeError(Exception):
    pass


@dataclass
class LinkRecord:
    code: str
    url: str
    owner_id: str
    created_at: float = field(default_factory=time.time)
    clicks: int = 0
    disabled: bool = False


class LinkStore:
    def __init__(self):
        self._by_code = {}
        self._by_owner_url = {}
        self._lock = threading.Lock()

    def save(self, code, url, owner_id):
        with self._lock:
            if code in self._by_code:
                raise DuplicateCodeError(code)
            record = LinkRecord(code=code, url=url, owner_id=owner_id)
            self._by_code[code] = record
            self._by_owner_url[(owner_id, url)] = code
            return record

    def get(self, code):
        return self._by_code.get(code)

    def find_by_url(self, url, owner_id):
        return self._by_owner_url.get((owner_id, url))

    def increment_clicks(self, code):
        with self._lock:
            record = self._by_code.get(code)
            if record:
                record.clicks += 1

    def disable(self, code, owner_id):
        with self._lock:
            record = self._by_code.get(code)
            if record is None:
                return False
            if record.owner_id != owner_id:
                raise PermissionError("not your link")
            record.disabled = True
            return True
