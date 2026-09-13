from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.domain import DomainRepository
from app.schemas.work_order import WorkOrderCreate, WorkOrderRead
from app.services.domain import DomainService

router = APIRouter(prefix="/work-orders", tags=["work-orders"])
repository = DomainRepository()
service = DomainService(repository)


@router.post("", response_model=WorkOrderRead, status_code=status.HTTP_201_CREATED)
def create_work_order(payload: WorkOrderCreate, db: Session = Depends(get_db)) -> WorkOrderRead:
    return service.create_work_order(db, payload)


@router.get("", response_model=list[WorkOrderRead])
def list_work_orders(db: Session = Depends(get_db)) -> list[WorkOrderRead]:
    return repository.list_work_orders(db)
