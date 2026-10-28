import importlib
import sys

import pytest
from werkzeug.security import generate_password_hash


def _login(client, email, password, role="member"):
    return client.post("/login", data={"email": email, "password": password, "role": role})


def _signup(client, **over):
    data = {"name": "A", "email": "a@x.com", "password": "pw12345!", "plan": "Basic"}
    data.update(over)
    return client.post("/signup", data=data)


def test_signup_stores_a_hash_not_the_password(gym):
    _signup(gym.app.test_client())
    row = gym.supabase.db["members"][0]
    assert row["password"] != "pw12345!" and gym.is_hashed(row["password"])


@pytest.mark.parametrize("plan", ["Admin", "admin", "", "Gold"])
def test_signup_rejects_plans_outside_the_allowlist(gym, plan):
    _signup(gym.app.test_client(), plan=plan)
    assert gym.supabase.db.get("members", []) == []


def test_signup_rejects_the_reserved_admin_email(gym):
    _signup(gym.app.test_client(), email="Admin@Gym.com")
    assert gym.supabase.db.get("members", []) == []


def test_hashed_member_can_log_in_and_wrong_password_cannot(gym):
    c = gym.app.test_client()
    _signup(c)
    assert _login(c, "a@x.com", "nope").headers["Location"].endswith("/login")
    with c.session_transaction() as s:
        assert "user" not in s
    _login(c, "a@x.com", "pw12345!")
    with c.session_transaction() as s:
        assert s["user"]["role"] == "member"


def test_legacy_plaintext_row_still_logs_in_and_is_upgraded_to_a_hash(gym):
    gym.supabase.db["members"] = [{"id": 1, "name": "Old", "email": "old@x.com", "password": "oldpw", "plan": "Basic"}]
    c = gym.app.test_client()
    _login(c, "old@x.com", "wrong")
    with c.session_transaction() as s:
        assert "user" not in s
    assert gym.supabase.db["members"][0]["password"] == "oldpw"  # a failed login changes nothing
    _login(c, "old@x.com", "oldpw")
    with c.session_transaction() as s:
        assert s["user"]["email"] == "old@x.com"
    assert gym.is_hashed(gym.supabase.db["members"][0]["password"])
    _login(gym.app.test_client(), "old@x.com", "oldpw")  # and the hash works afterwards


def test_existing_admin_row_still_gets_the_admin_role(gym):
    gym.supabase.db["members"] = [{"id": 9, "name": "Boss", "email": "admin@gym.com", "plan": "Admin",
                                   "password": generate_password_hash("adminpw")}]
    c = gym.app.test_client()
    _login(c, "admin@gym.com", "adminpw")
    with c.session_transaction() as s:
        assert s["user"]["role"] == "admin"


def test_trainer_login_uses_the_trainers_table(gym):
    gym.supabase.db["trainers"] = [{"id": 3, "name": "T", "email": "t@x.com", "password": generate_password_hash("tpw")}]
    c = gym.app.test_client()
    _login(c, "t@x.com", "tpw", role="trainer")
    with c.session_transaction() as s:
        assert s["user"]["role"] == "trainer"


def test_login_error_does_not_leak_internals(gym, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("SECRET-INTERNAL-DETAIL")
    monkeypatch.setattr(gym.supabase, "from_", boom)
    c = gym.app.test_client()
    r = c.post("/login", data={"email": "a@x.com", "password": "x", "role": "member"}, follow_redirects=True)
    assert b"SECRET-INTERNAL-DETAIL" not in r.data


def test_admin_pages_need_an_admin_session(gym):
    c = gym.app.test_client()
    assert c.get("/admin/members").status_code in (301, 302)


def test_startup_requires_credentials_and_a_fixed_secret(monkeypatch, gym):
    for var in ("SUPABASE_URL", "SUPABASE_KEY"):
        monkeypatch.delenv(var)
        sys.modules.pop("app", None)
        with pytest.raises(RuntimeError):
            importlib.import_module("app")
        monkeypatch.setenv(var, "x")
    monkeypatch.delenv("FLASK_SECRET_KEY")
    sys.modules.pop("app", None)
    with pytest.raises(RuntimeError):
        importlib.import_module("app")
    monkeypatch.setenv("FLASK_DEBUG", "1")
    sys.modules.pop("app", None)
    assert importlib.import_module("app").app.secret_key
