"""S3 兼容对象存储抽象。dev 用 MinIO，生产用 OSS(S3兼容)/S3。

看图走 presigned_get（浏览器直连，多实例无需共享盘）；
发 LLM 走 get → base64（敏感图不交公网 URL，口径统一）。
"""

from typing import Protocol

import aioboto3

from ai_engine.config import settings


class ObjectStore(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...
    async def get(self, key: str) -> bytes: ...
    async def presigned_get(self, key: str, ttl_seconds: int) -> str: ...


class S3ObjectStore:
    def __init__(self) -> None:
        self._session = aioboto3.Session()

    def _client(self):  # type: ignore[no-untyped-def]
        return self._session.client(
            "s3",
            endpoint_url=settings.object_store_endpoint,
            aws_access_key_id=settings.object_store_access_key,
            aws_secret_access_key=settings.object_store_secret_key,
            region_name=settings.object_store_region,
        )

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        async with self._client() as c:
            await c.put_object(
                Bucket=settings.object_store_bucket, Key=key, Body=data, ContentType=content_type
            )

    async def get(self, key: str) -> bytes:
        async with self._client() as c:
            resp = await c.get_object(Bucket=settings.object_store_bucket, Key=key)
            async with resp["Body"] as body:
                return await body.read()

    async def presigned_get(self, key: str, ttl_seconds: int) -> str:
        async with self._client() as c:
            return await c.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.object_store_bucket, "Key": key},
                ExpiresIn=ttl_seconds,
            )


_store: ObjectStore | None = None


def get_object_store() -> ObjectStore:
    global _store
    if _store is None:
        _store = S3ObjectStore()
    return _store


def set_object_store(store: ObjectStore) -> None:
    """测试替换用。"""
    global _store
    _store = store
