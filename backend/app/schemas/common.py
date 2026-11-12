"""Shared API schema primitives: pagination, sorting, ORM config."""

from __future__ import annotations

from typing import Generic, Sequence, TypeVar

from fastapi import Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class PageParams:
    def __init__(
        self,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=200),
        sort: str | None = Query(None, description="Field name, prefix with '-' for descending"),
        q: str | None = Query(None, max_length=200, description="Free-text search"),
    ):
        self.page = page
        self.page_size = page_size
        self.sort = sort
        self.q = q


def paginate(db: Session, stmt: Select, params: PageParams, *, sortable: dict[str, object], default_sort: object, mapper=None) -> dict:
    """Apply whitelisted sorting + pagination. `sortable` maps API field names to columns."""
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    order = default_sort
    if params.sort:
        desc = params.sort.startswith("-")
        key = params.sort.lstrip("-")
        col = sortable.get(key)
        if col is not None:
            order = col.desc() if desc else col.asc()  # type: ignore[attr-defined]
    rows: Sequence = db.scalars(stmt.order_by(order).offset((params.page - 1) * params.page_size).limit(params.page_size)).all()
    items = [mapper(r) for r in rows] if mapper else list(rows)
    return {
        "items": items,
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "pages": (total + params.page_size - 1) // params.page_size if total else 0,
    }


class Message(BaseModel):
    message: str
