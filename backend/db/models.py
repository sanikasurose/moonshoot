# SQLAlchemy models — mirror docs/TRD.md section 3 exactly.
from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class RawJob(Base):
    __tablename__ = "raw_jobs"

    id = Column(Integer, primary_key=True)
    source = Column(Text, nullable=False)
    raw_data = Column(JSONB, nullable=False)
    fetched_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    processed = Column(Boolean, server_default="false")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("company_name", "role_title", "location"),)

    id = Column(Integer, primary_key=True)
    company_name = Column(Text, nullable=False)
    role_title = Column(Text, nullable=False)
    location = Column(Text)
    country = Column(Text)
    is_remote = Column(Boolean, server_default="false")
    apply_url = Column(Text)
    source = Column(Text)
    date_posted = Column(Date)
    ats_platform = Column(Text)
    raw_description = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class JobScore(Base):
    __tablename__ = "job_scores"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    overall_score = Column(Numeric(3, 1))
    location_score = Column(Numeric(3, 1))
    visa_score = Column(Numeric(3, 1))
    company_tier_score = Column(Numeric(3, 1))
    remote_score = Column(Numeric(3, 1))
    tech_stack_score = Column(Numeric(3, 1))
    ai_reasoning = Column(Text)
    scored_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True)
    filename = Column(Text, nullable=False)
    s3_key = Column(Text, nullable=False)
    s3_url = Column(Text, nullable=False)
    role_type = Column(Text)
    target_company = Column(Text)
    notes = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    status = Column(Text, server_default="not_applied")
    date_applied = Column(Date)
    date_response = Column(Date)
    resume_id = Column(Integer, ForeignKey("resumes.id"))
    referral_name = Column(Text)
    referral_contact = Column(Text)
    notes = Column(Text)
    alerted_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class CorrespondenceLog(Base):
    __tablename__ = "correspondence_log"

    id = Column(Integer, primary_key=True)
    gmail_msg_id = Column(Text, nullable=False, unique=True)
    sender = Column(Text)
    subject = Column(Text)
    snippet = Column(Text)
    classification = Column(Text, server_default="personal_correspondence")
    received_at = Column(TIMESTAMP(timezone=True))
    logged_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    notified = Column(Boolean, server_default="false")


class AlertLog(Base):
    __tablename__ = "alert_log"

    id = Column(Integer, primary_key=True)
    alert_type = Column(Text)
    job_ids = Column(ARRAY(Integer))
    sent_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    status = Column(Text)
