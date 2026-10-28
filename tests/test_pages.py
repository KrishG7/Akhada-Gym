import pytest


@pytest.mark.parametrize("path", ["/login", "/signup"])
def test_public_pages_render(gym, path):
    r = gym.app.test_client().get(path)
    assert r.status_code == 200 and b"<form" in r.data


def test_signup_form_only_offers_the_allowed_plans(gym):
    html = gym.app.test_client().get("/signup").data.decode()
    for plan in gym.ALLOWED_PLANS:
        assert f'value="{plan}"' in html
    assert 'value="Admin"' not in html
