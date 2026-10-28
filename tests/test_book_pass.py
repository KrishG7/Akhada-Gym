import pytest

GOOD = {"name": "Guest", "phone": "9876543210", "email": "g@x.com", "bookingType": "one_day_pass"}


def book(gym, **over):
    return gym.app.test_client().post("/api/book_pass", json=dict(GOOD, **over))


def test_booking_is_recorded_as_pending_not_completed(gym):
    r = book(gym)
    assert r.status_code == 200 and r.get_json()["success"] is True
    row = gym.supabase.db["one_day_passes"][0]
    assert row["payment_status"] == "pending" and row["amount"] == 500 and len(row["otp"]) == 6


def test_gym_tour_is_allowed_and_priced(gym):
    assert book(gym, bookingType="gym_tour").status_code == 200
    assert gym.supabase.db["one_day_passes"][0]["amount"] == 200


@pytest.mark.parametrize("over", [{"bookingType": "free_for_life"}, {"phone": "abc"}, {"phone": "123"},
                                  {"email": "nope"}, {"name": "x" * 101}, {"name": ""}])
def test_bad_input_is_rejected_and_nothing_is_stored(gym, over):
    assert book(gym, **over).status_code == 400
    assert gym.supabase.db.get("one_day_passes", []) == []


def test_missing_body_is_a_400_not_a_crash(gym):
    assert gym.app.test_client().post("/api/book_pass", data="not json").status_code == 400


def test_a_phone_number_can_only_book_three_times_an_hour(gym):
    codes = [book(gym).status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    assert len(gym.supabase.db["one_day_passes"]) == 3


def test_one_address_is_limited_even_with_different_phones(gym):
    codes = [book(gym, phone=f"98765432{n:02d}").status_code for n in range(12)]
    assert codes[:10] == [200] * 10 and codes[10:] == [429, 429]


def test_server_errors_do_not_leak_exception_text(gym, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("SECRET-INTERNAL-DETAIL")
    monkeypatch.setattr(gym.supabase, "from_", boom)
    r = book(gym)
    assert r.status_code == 500 and "SECRET-INTERNAL-DETAIL" not in r.get_data(as_text=True)
