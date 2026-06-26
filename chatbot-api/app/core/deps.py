from typing import Any
from fastapi import Depends, Query
from dataclasses import dataclass
from app.core.config import settings


@dataclass
class PaginationParams:
    offset: int
    limit: int


def get_pagination(
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of items to return"),
) -> PaginationParams:
    return PaginationParams(offset=offset, limit=limit)


async def get_redis_client() -> Any:
    from app.core.redis import get_redis_client

    return get_redis_client()


async def get_token_blacklist(r_client: Any = Depends(get_redis_client)) -> Any:
    from app.modules.auth.utils.token_blacklist import TokenBlacklist

    return TokenBlacklist(r_client)


async def get_rate_limiter(r_client: Any = Depends(get_redis_client)) -> Any:
    from app.utils.rate_limiter import RateLimiter

    return RateLimiter(client=r_client)


async def get_semantic_cache(r_client: Any = Depends(get_redis_client)) -> Any:
    from app.utils.cache import SemanticCache

    return SemanticCache(vector_dim=settings.embedding_vector_size, client=r_client)


async def get_query_cache(r_client: Any = Depends(get_redis_client)) -> Any:
    from app.utils.cache import QueryEmbeddingCache

    return QueryEmbeddingCache(r_client, model_name=settings.embedding_hf_model)
