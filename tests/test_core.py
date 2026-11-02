from datetime import UTC

from app.core.config import Settings, load_settings
from app.core.hashing import sha256_hex
from app.core.time import utcnow


def test_core(monkeypatch):
    monkeypatch.setenv("SHOP_NAME", "Test Mart")
    load_settings.cache_clear()
    assert load_settings().shop_name == "Test Mart"
    assert load_settings() is load_settings()
    assert Settings(_env_file=None).currency == "NPR"
    assert utcnow().tzinfo == UTC
    assert sha256_hex("hello") == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    load_settings.cache_clear()
