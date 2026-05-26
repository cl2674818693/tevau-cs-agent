from ai_engine.storage import object_store as om


class FakeStore:
    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.data[key] = data

    async def get(self, key: str) -> bytes:
        return self.data[key]

    async def presigned_get(self, key: str, ttl_seconds: int) -> str:
        return f"https://signed.example/{key}?ttl={ttl_seconds}"


async def test_set_and_get_object_store_singleton():
    fake = FakeStore()
    om.set_object_store(fake)
    assert om.get_object_store() is fake
    await om.get_object_store().put("k", b"abc", "image/png")
    assert await om.get_object_store().get("k") == b"abc"
    url = await om.get_object_store().presigned_get("k", 300)
    assert "ttl=300" in url
