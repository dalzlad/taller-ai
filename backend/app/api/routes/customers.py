from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.domain import DomainRepository
from app.schemas.customer import CustomerCreate, CustomerRead
from app.services.domain import DomainService

router = APIRouter(prefix="/customers", tags=["customers"])
repository = DomainRepository()
service = DomainService(repository)


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)) -> CustomerRead:
    return service.create_customer(db, payload)


@router.get("", response_model=list[CustomerRead])
def list_customers(db: Session = Depends(get_db)) -> list[CustomerRead]:
    return repository.list_customers(db)
