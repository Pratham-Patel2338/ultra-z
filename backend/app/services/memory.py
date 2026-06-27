import json

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.entities import MemoryItem
from app.schemas.memory import MemoryCreate, MemoryUpdate


def _serialize_tags(tags: list[str]) -> str:
    return json.dumps([tag.strip() for tag in tags if tag and tag.strip()])


def _deserialize_tags(tags_json: str) -> list[str]:
    try:
        data = json.loads(tags_json)
        if isinstance(data, list):
            return [str(item) for item in data]
    except json.JSONDecodeError:
        return []
    return []


def create_memory_item(session: Session, payload: MemoryCreate) -> MemoryItem:
    memory_item = MemoryItem(
        title=payload.title,
        content=payload.content,
        namespace=payload.namespace,
        tags_json=_serialize_tags(payload.tags),
        source=payload.source,
    )
    session.add(memory_item)
    session.commit()
    session.refresh(memory_item)
    return memory_item


def update_memory_item(session: Session, memory_item: MemoryItem, payload: MemoryUpdate) -> MemoryItem:
    if payload.title is not None:
        memory_item.title = payload.title
    if payload.content is not None:
        memory_item.content = payload.content
    if payload.namespace is not None:
        memory_item.namespace = payload.namespace
    if payload.tags is not None:
        memory_item.tags_json = _serialize_tags(payload.tags)
    if payload.source is not None:
        memory_item.source = payload.source

    session.commit()
    session.refresh(memory_item)
    return memory_item


def delete_memory_item(session: Session, memory_item: MemoryItem) -> None:
    session.delete(memory_item)
    session.commit()


def list_memory_items(
    session: Session,
    query: str | None = None,
    namespace: str | None = None,
    limit: int = 50,
) -> list[MemoryItem]:
    statement = select(MemoryItem)
    if namespace:
        statement = statement.where(MemoryItem.namespace == namespace)
    if query:
        pattern = f"%{query}%"
        statement = statement.where(
            or_(
                MemoryItem.title.ilike(pattern),
                MemoryItem.content.ilike(pattern),
                MemoryItem.namespace.ilike(pattern),
                MemoryItem.tags_json.ilike(pattern),
            )
        )
    statement = statement.order_by(MemoryItem.updated_at.desc()).limit(limit)
    return list(session.scalars(statement).all())


def get_memory_item(session: Session, memory_id: int) -> MemoryItem | None:
    return session.get(MemoryItem, memory_id)


def memory_to_dict(memory_item: MemoryItem) -> dict:
    return {
        "id": memory_item.id,
        "title": memory_item.title,
        "content": memory_item.content,
        "namespace": memory_item.namespace,
        "tags": _deserialize_tags(memory_item.tags_json),
        "source": memory_item.source,
        "created_at": memory_item.created_at,
        "updated_at": memory_item.updated_at,
    }
