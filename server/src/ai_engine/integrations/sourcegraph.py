from typing import Any

import httpx

from ai_engine.config import settings

_SEARCH_QUERY = """
query Search($query: String!) {
  search(query: $query, version: V3) {
    results {
      results {
        __typename
        ... on FileMatch {
          repository { name }
          file { path }
          lineMatches { lineNumber preview }
        }
      }
    }
  }
}
"""


async def graphql_search(sg_query: str) -> dict[str, Any]:
    """调 Sourcegraph GraphQL search。返回原始 data 字段。"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.sourcegraph_url}/.api/graphql",
            json={"query": _SEARCH_QUERY, "variables": {"query": sg_query}},
            headers={"Authorization": f"token {settings.sourcegraph_token}"},
        )
    if resp.status_code != 200:
        raise RuntimeError(f"sourcegraph search failed: {resp.status_code} {resp.text[:200]}")
    data: dict[str, Any] = resp.json()
    return data


async def raw_file(repo_sg: str, rev: str, path: str) -> bytes:
    """走 Sourcegraph raw API 读文件内容。"""
    url = f"{settings.sourcegraph_url}/{repo_sg}@{rev}/-/raw/{path}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            url, headers={"Authorization": f"token {settings.sourcegraph_token}"}
        )
    if resp.status_code == 404:
        raise FileNotFoundError(f"{repo_sg}@{rev}:{path}")
    if resp.status_code != 200:
        raise RuntimeError(f"sourcegraph raw failed: {resp.status_code}")
    return resp.content
