"""Shared capacity for direct HTTP analyses and server-side review workflows."""
from contextlib import contextmanager
from fastapi import HTTPException


@contextmanager
def analysis_capacity():
    from api import review_routes
    workers = review_routes.store.workers
    if not workers.acquire(blocking=False):
        raise HTTPException(429, 'Analysis capacity is busy. Retry shortly.')
    try:
        yield
    finally:
        workers.release()


def require_analysis_capacity():
    with analysis_capacity():
        yield
