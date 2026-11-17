import base64
import io
import zipfile

import pytest

from viva.repo import RepoError, is_candidate, load_from_github, load_from_zip, parse_github_url


@pytest.mark.parametrize("url,expected", [
    ("https://github.com/racks1401/Product-Recommendation-System", ("racks1401", "Product-Recommendation-System", None)),
    ("github.com/a/b.git", ("a", "b", None)),
    ("https://github.com/a/b/tree/dev/src", ("a", "b", "dev")),
    ("https://www.github.com/a/b/", ("a", "b", None)),
])
def test_parse_github_url(url, expected):
    assert parse_github_url(url) == expected


def test_parse_rejects_other_hosts():
    with pytest.raises(RepoError):
        parse_github_url("https://gitlab.com/a/b")


@pytest.mark.parametrize("path,size,ok", [
    ("app/views.py", 2000, True),
    ("node_modules/x/index.js", 2000, False),
    ("static/app.min.js", 2000, False),
    ("README.md", 2000, False),
    ("app/tiny.py", 20, False),
    ("app/huge.py", 500_000, False),
    ("proj/migrations/0001_initial.py", 2000, False),
])
def test_is_candidate(path, size, ok):
    assert is_candidate(path, size) is ok


def _zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, text in files.items():
            zf.writestr(name, text)
    return buf.getvalue()


def test_zip_strips_github_top_folder():
    body = "def f(x):\n    return x\n" * 10
    files = load_from_zip(_zip({"repo-main/src/core.py": body, "repo-main/README.md": "hi"}))
    assert [f.path for f in files] == ["src/core.py"]


def test_zip_without_code_raises():
    with pytest.raises(RepoError):
        load_from_zip(_zip({"a/README.md": "hello"}))


class FakeResp:
    def __init__(self, status, data):
        self.status_code, self._data = status, data

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append(url)
        for suffix, resp in self.routes.items():
            if url.endswith(suffix):
                return resp
        return FakeResp(404, {})


def test_load_from_github_with_fake_api():
    body = "def handler(req):\n    if not req:\n        return None\n    return req.body\n" * 5
    routes = {
        "/repos/o/r": FakeResp(200, {"default_branch": "main"}),
        "/git/trees/main": FakeResp(200, {"tree": [
            {"type": "blob", "path": "api/handlers.py", "size": len(body)},
            {"type": "blob", "path": "node_modules/x.js", "size": 500},
            {"type": "tree", "path": "api"},
        ]}),
        "/contents/api/handlers.py": FakeResp(200, {"content": base64.b64encode(body.encode()).decode()}),
    }
    files = load_from_github("https://github.com/o/r", session=FakeSession(routes))
    assert len(files) == 1 and files[0].path == "api/handlers.py" and "handler" in files[0].content


def test_rate_limit_message():
    with pytest.raises(RepoError, match="rate limit"):
        load_from_github("https://github.com/o/r", session=FakeSession({"/repos/o/r": FakeResp(403, {})}))
