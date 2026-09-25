"""Reporting queries."""
from typing import List
import logging

from sqlalchemy import select, func, desc, asc
from sqlalchemy.orm import Session

from app.models import Book, Order, OrderItem, OrderStatus
from app.schemas import TopBook
from app.cache import get_cache, set_cache

logger = logging.getLogger(__name__)


def top_books(db: Session, limit: int = 5) -> List[TopBook]:
    """Best-selling books.

    Rules: copies_sold sums quantities over ``paid`` orders only; books with no sales are
    excluded; sorted by copies_sold desc, then title asc; at most ``limit`` rows.
    """
    cache_key = f"top_books:{limit}"
    
    # 1. Try to get from cache
    cached_data = get_cache(cache_key)
    if cached_data:
        logger.info(f"Cache HIT for {cache_key}")
        return [TopBook(**item) for item in cached_data]
        
    logger.info(f"Cache MISS for {cache_key}")

    query = (
        select(
            Book.id.label("book_id"),
            Book.title.label("title"),
            func.sum(OrderItem.quantity).label("copies_sold"),
        )
        .join(OrderItem, OrderItem.book_id == Book.id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.status == OrderStatus.PAID.value)
        .group_by(Book.id, Book.title)
        .order_by(desc("copies_sold"), asc(Book.title))
        .limit(limit)
    )

    rows = db.execute(query).all()
    results = [TopBook(book_id=r.book_id, title=r.title, copies_sold=r.copies_sold) for r in rows]
    
    # 2. Save to cache for 5 minutes (300 seconds)
    set_cache(cache_key, [r.model_dump() for r in results], ttl_seconds=300)
    
    return results
