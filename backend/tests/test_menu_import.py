"""Menu photo import, with Claude faked: nothing here talks to the real API."""
import io
from types import SimpleNamespace

import pytest
from PIL import Image

from app.core import menu_ai
from app.core.config import settings


def png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(buffer, format="PNG")
    return buffer.getvalue()


DRAFT = menu_ai.MenuDraft(categories=[
    menu_ai.DraftCategory(name="Lanches", products=[
        menu_ai.DraftProduct(name="X-Bacon", description="Pão, hambúrguer, bacon", price=28.9),
        menu_ai.DraftProduct(name="Batata", price=15, sizes=[menu_ai.DraftSize(name="Média", price=15), menu_ai.DraftSize(name="Grande", price=22.5)]),
    ]),
    menu_ai.DraftCategory(name="Vazia", products=[]),
])


@pytest.fixture
def fake_claude(monkeypatch):
    calls = []

    class FakeMessages:
        def parse(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(parsed_output=DRAFT.model_copy(deep=True), stop_reason="end_turn")

    monkeypatch.setattr(settings, "anthropic_api_key", "fake-key")
    monkeypatch.setattr(menu_ai.anthropic, "Anthropic", lambda **_: SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages())))
    return calls


def read(client, shop, *files):
    return client.post("/menu-import/read", files=[("files", (f"f{i}", raw, "image/png")) for i, raw in enumerate(files)], headers=shop.auth_headers)


def test_read_returns_a_draft_and_saves_nothing(make_tenant, client, fake_claude):
    shop = make_tenant(plan=None)
    response = read(client, shop, png())
    assert response.status_code == 200, response.text
    categories = response.json()["categories"]
    assert [c["name"] for c in categories] == ["Lanches"]  # empty categories dropped
    assert fake_claude[0]["messages"][0]["content"][0]["type"] == "image"
    assert shop.get("/products").json() == []
    assert read(client, shop, b"not an image").status_code == 422
    assert read(client, shop, *[png()] * 5).status_code == 422  # at most 4 files


def test_read_is_hidden_without_api_key(make_tenant, client, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    assert client.get("/platform/plans").json()["menu_import"] is False
    shop = make_tenant()
    assert read(client, shop, png()).status_code == 422


def test_apply_respects_the_trial_limit_by_hiding_the_extra_products(make_tenant, client):
    shop = make_tenant(plan=None)  # trial: 10 active products
    shop.add_product(name="Já existia")
    products = [{"name": f"Espetinho {i}", "price": "9.00"} for i in range(11)]
    payload = {"categories": [
        {"name": "Espetinhos", "products": products},
        {"name": "Porções", "products": [{"name": "Batata", "price": "22.50", "sizes": [{"name": "Média", "price": "15.00"}, {"name": "Grande", "price": "22.50"}]}]},
    ]}
    result = shop.post("/menu-import/apply", payload)
    assert result.status_code == 200, result.text
    assert result.json() == {"created": 12, "hidden": 3, "categories": 2}
    items = shop.get("/products").json()
    assert sum(p["active"] for p in items) == 10
    batata = next(p for p in items if p["name"] == "Batata")
    assert batata["price"] == "15.00" and batata["active"] is False
    sizes = batata["options"][0]
    assert sizes["required"] and [(o["name"], o["price"]) for o in sizes["options"]] == [("Média", "0.00"), ("Grande", "7.50")]


def test_operator_cannot_import(make_tenant, client):
    shop = make_tenant()
    shop.post("/users", {"name": "Op", "email": f"op@{shop.slug}.com", "password": "senha-segura-123", "role": "OPERATOR"})
    operator = type(shop)(client, shop.slug, f"op@{shop.slug}.com")
    operator.login(password="senha-segura-123")
    assert operator.post("/menu-import/apply", {"categories": [{"name": "X", "products": [{"name": "Y", "price": "1.00"}]}]}).status_code == 403
