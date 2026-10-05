"""Images go to the bucket (Cloudflare R2) when it is configured; the bucket client is faked here."""
import pytest

from app.core import storage
from app.core.config import settings
from tests.test_features import png_bytes

PUBLIC = "https://fotos.exemplo.com"


@pytest.fixture
def bucket(monkeypatch):
    files: dict[str, bytes] = {}
    for name, value in (("r2_account_id", "acc"), ("r2_access_key_id", "key"), ("r2_secret_access_key", "secret"),
                        ("r2_bucket", "fotos"), ("media_public_url", PUBLIC)):
        monkeypatch.setattr(settings, name, value)
    monkeypatch.setattr(storage, "put_object", lambda key, data, content_type: files.__setitem__(key, data))
    monkeypatch.setattr(storage, "delete_object", lambda key: files.pop(key))
    return files


def test_upload_goes_to_bucket_and_is_removed_when_replaced(make_tenant, client, bucket):
    shop = make_tenant()
    upload = client.post("/media", files={"file": ("x.png", png_bytes((40, 30)), "image/png")}, headers=shop.auth_headers)
    assert upload.status_code == 201, upload.text
    url = upload.json()["url"]
    assert url.startswith(f"{PUBLIC}/") and url.endswith(".webp")
    assert len(bucket) == 1 and upload.json()["used_bytes"] > 0

    product = shop.add_product(image_url=url)
    assert shop.public_get("/public/menu").json()["products"][0]["image_url"] == url
    # The old /media/<id> address still leads to the file.
    media_id = url.rsplit("/", 1)[-1].removesuffix(".webp")
    assert client.get(f"/media/{media_id}", follow_redirects=False).headers["location"] == url

    assert shop.patch(f"/products/{product['id']}", {"image_url": None}).status_code == 200
    assert bucket == {}
    assert shop.get("/media-usage").json()["used_bytes"] == 0


def test_database_storage_is_the_default(make_tenant, client):
    shop = make_tenant()
    upload = client.post("/media", files={"file": ("x.png", png_bytes((20, 20)), "image/png")}, headers=shop.auth_headers)
    url = upload.json()["url"]
    assert url.startswith("/media/")
    assert client.get(url).headers["content-type"] == "image/webp"
