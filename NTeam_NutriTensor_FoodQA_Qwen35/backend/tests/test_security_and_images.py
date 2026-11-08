from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone

import pytest
from PIL import Image

from nutritensor.core.config import ConfigurationError, Settings
from nutritensor.core.errors import InvalidImage, NotFound
from nutritensor.core.security import RateLimiter, hash_password, token_digest, verify_password
from nutritensor.services.images import ImageService


def image_bytes(format="JPEG", size=(300, 200)):
    buffer = io.BytesIO()
    Image.new("RGB", size, (120, 150, 100)).save(buffer, format=format)
    return buffer.getvalue()


def test_password_hash_has_random_salt_and_constant_verification():
    left = hash_password("long test password")
    right = hash_password("long test password")
    assert left != right
    assert verify_password("long test password", left)
    assert not verify_password("wrong password", left)
    assert not verify_password("anything", "broken")
    assert "long test password" not in left


def test_session_hash_is_keyed_and_does_not_expose_token():
    assert token_digest("token", "secret-a") != token_digest("token", "secret-b")
    assert len(token_digest("token", "secret-a")) == 64


def test_rate_limiter_rollover_and_key_bound():
    limiter = RateLimiter(2, window_seconds=60, max_keys=2)
    assert limiter.check("a", now=0).allowed
    assert limiter.check("a", now=1).allowed
    assert not limiter.check("a", now=2).allowed
    assert limiter.check("a", now=61).allowed
    limiter.check("b", now=62)
    limiter.check("c", now=63)
    assert len(limiter._buckets) == 2


def test_live_mode_fails_closed_without_credentials(tmp_path):
    # Use an isolated path instead of the project's real users.json.
    with pytest.raises(ConfigurationError, match="admin password"):
        Settings(
            mode="live",
            model_backend="transformers",
            model_path="test",
            users_path=tmp_path / "missing-users.json",
            admin_password="",
            admin_password_hash="",
        ).validate()


def test_production_refuses_insecure_cookies():
    with pytest.raises(ConfigurationError, match="HTTPS"):
        Settings(environment="production").validate()


def test_remote_inference_requires_explicit_opt_in():
    with pytest.raises(ConfigurationError, match="Remote inference"):
        Settings(model_backend="openai-compatible", remote_llm_url="https://example.com/v1").validate()


def test_credentials_in_url_are_rejected():
    with pytest.raises(ConfigurationError, match="Credentials"):
        Settings(model_backend="openai-compatible", remote_llm_url="http://name:secret@127.0.0.1/v1").validate()


def test_image_decoding_resize_and_metadata_stripping(settings, database):
    service = ImageService(settings, database)
    original = Image.new("RGB", (2000, 1400))
    exif = Image.Exif()
    exif[315] = "private owner"
    buffer = io.BytesIO()
    original.save(buffer, "JPEG", exif=exif)
    record = service.save("alice", buffer.getvalue())
    assert record["width"] <= 1280
    assert record["height"] <= 1280
    with Image.open(service.path("alice", record["id"])) as clean:
        assert not clean.getexif()
        assert clean.mode == "RGB"
    with pytest.raises(NotFound):
        service.path("bob", record["id"])


@pytest.mark.parametrize("payload", [b"", b"not an image", b"<svg onload='alert(1)'/>"])
def test_non_images_are_rejected(settings, database, payload):
    with pytest.raises(InvalidImage):
        ImageService(settings, database).save("alice", payload)


def test_unsupported_image_format_is_rejected(settings, database):
    with pytest.raises(InvalidImage):
        ImageService(settings, database).save("alice", image_bytes("BMP"))


def test_animated_image_is_rejected(settings, database):
    buffer = io.BytesIO()
    first = Image.new("RGB", (50, 50), "green")
    second = Image.new("RGB", (50, 50), "red")
    first.save(buffer, "WEBP", save_all=True, append_images=[second], duration=100)
    with pytest.raises(InvalidImage):
        ImageService(settings, database).save("alice", buffer.getvalue())


def test_expired_images_remove_bytes_and_rows(settings, database):
    service = ImageService(settings, database)
    record = service.save("alice", image_bytes())
    path = service.path("alice", record["id"])
    old = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    with database.connection(write=True) as connection:
        connection.execute("UPDATE images SET created_at=?", (old,))
    assert service.cleanup() == 1
    assert not path.exists()
    with pytest.raises(NotFound):
        database.get_image(record["id"], "alice")


def test_expired_session_is_unusable(database):
    database.create_session("hash", "alice", "csrf", "2000-01-01T00:00:00+00:00")
    assert database.get_session("hash") is None
