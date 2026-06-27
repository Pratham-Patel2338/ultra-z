from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_subject, get_database_session
from app.schemas.memory import MemoryCreate, MemoryRead, MemoryUpdate
from app.services.memory import (
    create_memory_item,
    delete_memory_item,
    get_memory_item,
    list_memory_items,
    memory_to_dict,
    update_memory_item,
)

router = APIRouter()


@router.get("", response_model=list[MemoryRead])
def read_memories(
    session: Session = Depends(get_database_session),
    subject: str = Depends(get_current_subject),
) -> list[MemoryRead]:
    _ = subject
    return [MemoryRead(**memory_to_dict(item)) for item in list_memory_items(session)]


@router.post("", response_model=MemoryRead, status_code=status.HTTP_201_CREATED)
def create_memory(
    payload: MemoryCreate,
    session: Session = Depends(get_database_session),
    subject: str = Depends(get_current_subject),
) -> MemoryRead:
    _ = subject
    item = create_memory_item(session, payload)
    return MemoryRead(**memory_to_dict(item))


@router.get("/{memory_id}", response_model=MemoryRead)
def read_memory(
    memory_id: int,
    session: Session = Depends(get_database_session),
    subject: str = Depends(get_current_subject),
) -> MemoryRead:
    _ = subject
    item = get_memory_item(session, memory_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory item not found")
    return MemoryRead(**memory_to_dict(item))


@router.patch("/{memory_id}", response_model=MemoryRead)
def update_memory(
    memory_id: int,
    payload: MemoryUpdate,
    session: Session = Depends(get_database_session),
    subject: str = Depends(get_current_subject),
) -> MemoryRead:
    _ = subject
    item = get_memory_item(session, memory_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory item not found")
    updated = update_memory_item(session, item, payload)
    return MemoryRead(**memory_to_dict(updated))


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(
    memory_id: int,
    session: Session = Depends(get_database_session),
    subject: str = Depends(get_current_subject),
) -> None:
    _ = subject
    item = get_memory_item(session, memory_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory item not found")
    delete_memory_item(session, item)
