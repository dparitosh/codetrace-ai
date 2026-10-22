"""Shared capacity for direct HTTP analyses and server-side review workflows."""
from contextlib import contextmanager
from fastapi import HTTPException


@contextmanager
def analysis_capacity():
    from api import review_routes
    workers = review_routes.store.workers
    if not workers.acquire(blocking=False):
        raise HTTPException(429, 'Analysis capacity is busy. Retry shortly.')
    # A synchronous FastAPI yield dependency may be entered and finalized by
    # different pool workers. Capture ownership in the generator, not the thread.
    lease = getattr(getattr(workers, 'local', None), 'lease', None)
    try:
        yield
    finally:
        if lease is None:
            workers.release()
        else:
            workers.release(lease=lease)


def require_analysis_capacity():
    with analysis_capacity():
        yield
