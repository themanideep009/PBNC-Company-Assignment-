"""Common Pydantic schemas: pagination, standard responses."""

from typing import Generic, List, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Query parameters for paginated list endpoints."""
    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response envelope."""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str
    detail: Optional[str] = None
