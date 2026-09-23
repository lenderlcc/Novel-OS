from dataclasses import asdict

from sqlalchemy import func, or_, select

from novel_os.domain.enums import ActorType, Authority, Status
from novel_os.domain.writing_profile import ProjectWritingProfile, WritingPreferences
from novel_os.models.writing_profile import ProjectWritingProfileModel as Model


class WritingProfileRepository:
    def __init__(self, session):
        self.session = session

    @staticmethod
    def snapshot(row):
        if row is None:
            return None
        values = {column.name: getattr(row, column.name) for column in Model.__table__.columns}
        values.update(
            preferences=WritingPreferences.from_payload(row.preferences),
            status=Status(row.status),
            source=ActorType(row.source),
            authority_level=Authority(row.authority_level),
        )
        return ProjectWritingProfile(**values)

    def get(self, project_id, *, approved=False, version=None):
        query = select(Model).where(Model.project_id == project_id)
        if approved:
            query = query.where(Model.status == Status.APPROVED)
        if version is not None:
            query = query.where(Model.version == version)
        return self.snapshot(self.session.scalar(query.order_by(Model.version.desc()).limit(1)))

    def versions(self, project_id, limit=100, offset=0):
        rows = self.session.scalars(
            select(Model)
            .where(Model.project_id == project_id)
            .order_by(Model.version.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self.snapshot(row) for row in rows]

    def state(self, project_id):
        latest = (
            select(func.max(Model.version)).where(Model.project_id == project_id).scalar_subquery()
        )
        rows = self.session.scalars(
            select(Model)
            .where(
                Model.project_id == project_id,
                or_(Model.version == latest, Model.status == Status.APPROVED),
            )
            .order_by(Model.version.desc())
        ).all()
        return (
            self.snapshot(rows[0]) if rows else None,
            next((self.snapshot(row) for row in rows if row.status == Status.APPROVED), None),
        )

    def add(self, record):
        values = asdict(record)
        values["preferences"] = record.preferences.payload()
        self.session.add(Model(**values))
        self.session.flush()
        return record

    def lifecycle(self, record):
        row = self.session.scalar(
            select(Model).where(Model.project_id == record.project_id, Model.id == record.id)
        )
        row.status, row.approved_at, row.approved_by = (
            record.status,
            record.approved_at,
            record.approved_by,
        )
        self.session.flush()
        return self.snapshot(row)
