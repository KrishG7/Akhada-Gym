import importlib
import os
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))


class _Result:
    def __init__(self, data):
        self.data, self.error = data, None


class _Query:
    def __init__(self, db, table):
        self.db, self.table, self.rows_filter, self.op, self.payload = db, table, [], "select", None

    def select(self, *_a, **_k):
        return self

    def eq(self, col, val):
        self.rows_filter.append((col, val))
        return self

    def insert(self, payload):
        self.op, self.payload = "insert", payload
        return self

    def update(self, payload):
        self.op, self.payload = "update", payload
        return self

    def _match(self, row):
        return all(row.get(c) == v for c, v in self.rows_filter)

    def execute(self):
        rows = self.db.setdefault(self.table, [])
        if self.op == "insert":
            row = dict(self.payload, id=len(rows) + 1)
            rows.append(row)
            return _Result([row])
        if self.op == "update":
            hit = [r for r in rows if self._match(r)]
            for r in hit:
                r.update(self.payload)
            return _Result(hit)
        return _Result([dict(r) for r in rows if self._match(r)])


class FakeSupabase:
    def __init__(self):
        self.db = {}

    def from_(self, table):
        return _Query(self.db, table)

    table = from_


@pytest.fixture()
def gym(monkeypatch):
    fake_mod = types.ModuleType("supabase")
    fake_mod.Client = object
    fake_mod.create_client = lambda url, key: FakeSupabase()
    monkeypatch.setitem(sys.modules, "supabase", fake_mod)
    monkeypatch.setenv("SUPABASE_URL", "http://example.test")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret")
    monkeypatch.syspath_prepend(ROOT)
    sys.modules.pop("app", None)
    module = importlib.import_module("app")
    module.app.config["TESTING"] = True
    yield module
    sys.modules.pop("app", None)
