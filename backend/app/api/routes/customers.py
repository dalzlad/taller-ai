from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.domain import DEFAULT_SEARCH_LIMIT, MAX_SEARCH_LIMIT, DomainRepository
from app.schemas.customer import CustomerCreate, CustomerRead
from app.services.domain import DomainService

router = APIRouter(prefix="/customers", tags=["customers"])
repository = DomainRepository()
service = DomainService(repository)


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)) -> CustomerRead:
    return service.create_customer(db, payload)


@router.get("", response_model=list[CustomerRead])
def list_customers(
    q: Annotated[
        str | None,
        Query(min_length=2, max_length=100, description="Partial match on name, phone or email"),
    ] = None,
    limit: Annotated[
        int | None,
        Query(ge=1, le=MAX_SEARCH_LIMIT, description=f"Defaults to {DEFAULT_SEARCH_LIMIT} when searching"),
    ] = None,
    db: Session = Depends(get_db),
) -> list[CustomerRead]:
    """Without parameters every customer is returned, as before searching existed."""
    if q is None:
        return repository.list_customers(db, limit=limit)
    query = q.strip()
    if len(query) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Search text must have at least 2 non-blank characters",
        )
    return repository.search_customers(db, query, limit or DEFAULT_SEARCH_LIMIT)
