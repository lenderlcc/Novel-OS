"""Flush-only persistence for immutable versions and derived approval pointers."""

from dataclasses import asdict

from sqlalchemy import func, or_, select

from novel_os.domain.character_profile import CharacterBehaviorProfile
from novel_os.domain.enums import ActorType, Authority, Status
from novel_os.models.character_profile import CharacterBehaviorProfileModel as Model


class CharacterProfileRepository:
    def __init__(self, session):
        self.session = session

    @staticmethod
    def snapshot(row):
        if row is None:
            return None
        values = {column.name: getattr(row, column.name) for column in Model.__table__.columns}
        values.update(
            status=Status(row.status),
            source=ActorType(row.source),
            authority_level=Authority(row.authority_level),
        )
        return CharacterBehaviorProfile(**values)

    def get(self, project_id, character_id, *, approved=False, version=None):
        query = select(Model).where(
            Model.project_id == project_id, Model.character_id == character_id
        )
        if approved:
            query = query.where(Model.status == Status.APPROVED)
        if version is not None:
            query = query.where(Model.version == version)
        return self.snapshot(self.session.scalar(query.order_by(Model.version.desc()).limit(1)))

    def approved_for_characters(self, project_id, character_ids):
        rows = self.session.scalars(
            select(Model)
            .where(
                Model.project_id == project_id,
                Model.character_id.in_(character_ids),
                Model.status == Status.APPROVED,
            )
            .order_by(Model.character_id)
        )
        return [self.snapshot(row) for row in rows]

    def versions(self, project_id, character_id, limit=100, offset=0):
        rows = self.session.scalars(
            select(Model)
            .where(Model.project_id == project_id, Model.character_id == character_id)
            .order_by(Model.version.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self.snapshot(row) for row in rows]

    def state(self, project_id, character_id):
        latest = (
            select(func.max(Model.version))
            .where(Model.project_id == project_id, Model.character_id == character_id)
            .scalar_subquery()
        )
        rows = self.session.scalars(
            select(Model)
            .where(
                Model.project_id == project_id,
                Model.character_id == character_id,
                or_(Model.version == latest, Model.status == Status.APPROVED),
            )
            .order_by(Model.version.desc())
        ).all()
        return (
            self.snapshot(rows[0]) if rows else None,
            next((self.snapshot(row) for row in rows if row.status == Status.APPROVED), None),
        )

    def add(self, record):
        self.session.add(Model(**asdict(record)))
        self.session.flush()
        return record

    def lifecycle(self, record):
        row = self.session.scalar(
            select(Model).where(Model.project_id == record.project_id, Model.id == record.id)
        )
        row.status, row.authority_level, row.approved_at, row.approved_by = (
            record.status,
            record.authority_level,
            record.approved_at,
            record.approved_by,
        )
        self.session.flush()
        return self.snapshot(row)
