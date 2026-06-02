"""Storage: object_store.py — S3 兼容存储抽象 + 全局单例管理。

策略：用一个假 client（实现 async with + put_object/get_object/head_bucket/
create_bucket/generate_presigned_url）替换 S3ObjectStore._client，避免真连 boto3。
ensure_bucket 的 404/NoSuchBucket → 触发 create_bucket；其他错抛出。
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from botocore.exceptions import ClientError

from ai_engine.storage import object_store
from ai_engine.storage.object_store import (
    S3ObjectStore,
    ensure_bucket,
    get_object_store,
    set_object_store,
)


class _FakeBody:
    def __init__(self, data: bytes) -> None:
        self._data = data

    async def __aenter__(self) -> "_FakeBody":
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def read(self) -> bytes:
        return self._data


class _FakeS3Client:
    """模拟 aioboto3 异步 S3 client。仅实现被测代码使用的方法。"""

    def __init__(self) -> None:
        self.put_calls: list[dict[str, object]] = []
        self.objects: dict[str, bytes] = {}
        self.head_responses: list[object] = []  # 顺序消费：抛 ClientError or None
        self.created_buckets: list[str] = []
        self.presigned_responses: list[str] = []

    async def put_object(self, **kwargs: object) -> None:
        self.put_calls.append(kwargs)
        self.objects[str(kwargs["Key"])] = bytes(kwargs["Body"])  # type: ignore[arg-type]

    async def get_object(self, **kwargs: object) -> dict[str, object]:
        data = self.objects.get(str(kwargs["Key"]), b"")
        return {"Body": _FakeBody(data)}

    async def head_bucket(self, **_: object) -> None:
        if self.head_responses:
            r = self.head_responses.pop(0)
            if isinstance(r, BaseException):
                raise r

    async def create_bucket(self, **kwargs: object) -> None:
        self.created_buckets.append(str(kwargs["Bucket"]))

    async def generate_presigned_url(self, *args: object, **kwargs: object) -> str:
        if self.presigned_responses:
            return self.presigned_responses.pop(0)
        return "https://example.com/signed"


@pytest.fixture
def fake_client():
    return _FakeS3Client()


@pytest.fixture
def patched_store(monkeypatch, fake_client):
    """构造一个 S3ObjectStore，其 _client() 返回 async-with 包裹的 fake_client。"""
    store = S3ObjectStore()

    @asynccontextmanager
    async def _ctx() -> AsyncIterator[_FakeS3Client]:
        yield fake_client

    monkeypatch.setattr(store, "_client", lambda: _ctx())
    return store


class TestPut:
    async def test_put_sends_to_bucket(self, patched_store, fake_client, monkeypatch) -> None:
        from ai_engine.config import settings

        monkeypatch.setattr(settings, "object_store_bucket", "test-bucket")
        await patched_store.put("k/1", b"hello", "text/plain")
        assert fake_client.put_calls[0]["Bucket"] == "test-bucket"
        assert fake_client.put_calls[0]["Key"] == "k/1"
        assert fake_client.put_calls[0]["Body"] == b"hello"
        assert fake_client.put_calls[0]["ContentType"] == "text/plain"


class TestGet:
    async def test_get_reads_body(self, patched_store, fake_client, monkeypatch) -> None:
        from ai_engine.config import settings

        monkeypatch.setattr(settings, "object_store_bucket", "test-bucket")
        fake_client.objects["k/1"] = b"data"
        out = await patched_store.get("k/1")
        assert out == b"data"

    async def test_get_missing_returns_empty(self, patched_store, fake_client, monkeypatch) -> None:
        from ai_engine.config import settings

        monkeypatch.setattr(settings, "object_store_bucket", "test-bucket")
        # fake_client 默认空映射 → 返回空字节
        assert await patched_store.get("missing") == b""


class TestPresignedGet:
    async def test_returns_url(self, patched_store, fake_client) -> None:
        fake_client.presigned_responses.append("https://signed.example/key?token=x")
        url = await patched_store.presigned_get("k", ttl_seconds=300)
        assert url.startswith("https://")


class TestEnsureBucket:
    async def test_bucket_exists_no_create(self, patched_store, fake_client) -> None:
        # head_bucket 默认不抛错（responses 空 → 视为存在）
        await patched_store.ensure_bucket()
        assert fake_client.created_buckets == []

    async def test_creates_on_404(self, patched_store, fake_client) -> None:
        fake_client.head_responses.append(
            ClientError({"Error": {"Code": "404", "Message": "not found"}}, "HeadBucket")
        )
        await patched_store.ensure_bucket()
        assert len(fake_client.created_buckets) == 1

    async def test_creates_on_no_such_bucket(self, patched_store, fake_client) -> None:
        fake_client.head_responses.append(
            ClientError(
                {"Error": {"Code": "NoSuchBucket", "Message": "no"}}, "HeadBucket"
            )
        )
        await patched_store.ensure_bucket()
        assert len(fake_client.created_buckets) == 1

    async def test_other_error_propagates(self, patched_store, fake_client) -> None:
        fake_client.head_responses.append(
            ClientError({"Error": {"Code": "AccessDenied", "Message": "no"}}, "HeadBucket")
        )
        with pytest.raises(ClientError):
            await patched_store.ensure_bucket()


class TestSingleton:
    def test_get_object_store_returns_same_instance(self) -> None:
        # 清空先
        object_store._store = None
        a = get_object_store()
        b = get_object_store()
        assert a is b
        # 都是 S3ObjectStore
        assert isinstance(a, S3ObjectStore)

    def test_set_object_store_overrides(self) -> None:
        class Fake:
            pass

        fake = Fake()
        set_object_store(fake)  # type: ignore[arg-type]
        assert get_object_store() is fake
        # 复位避免影响其他测试
        object_store._store = None


class TestEnsureBucketTopLevel:
    async def test_skip_when_fake_store(self) -> None:
        """fake store 不是 S3ObjectStore → ensure_bucket() 直接返回，不调用任何 boto。"""

        class Fake:
            async def put(self, *a, **k):  # pragma: no cover - 不会被调
                pass

            async def get(self, *a, **k):  # pragma: no cover
                pass

            async def presigned_get(self, *a, **k):  # pragma: no cover
                return ""

        set_object_store(Fake())  # type: ignore[arg-type]
        await ensure_bucket()  # 不应抛错也不应触 S3 路径
        object_store._store = None
