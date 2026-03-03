"""
Nubo Hub — SQLAlchemy Models (Source of Truth for DB Schema)

These models define ALL tables in the Nubo Hub database.
On server startup, `ensure_schema()` from `engine.py` will create
any missing tables automatically.

NOTE: This does NOT alter existing tables. If you add a new column
to an existing model, you need to run a migration or ALTER TABLE manually.
New TABLES, however, are auto-created.
"""

from sqlalchemy import (
    Column, Text, Boolean, Integer, Float, DateTime, Date,
    ForeignKey, UniqueConstraint, Index, func, text as sa_text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import DeclarativeBase, relationship
import uuid


class Base(DeclarativeBase):
    pass


# ============================================================
# Geolocation & Reference Data
# ============================================================

class State(Base):
    __tablename__ = "states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uf = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=False)


class City(Base):
    __tablename__ = "cities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    state = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)


# ============================================================
# Institutions & Courses
# ============================================================

class Institution(Base):
    __tablename__ = "institutions"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    name = Column(Text)
    code = Column(Text)
    type = Column(Text)
    category = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Campus(Base):
    __tablename__ = "campus"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    institution_id = Column(UUID(as_uuid=True), ForeignKey("institutions.id"))
    name = Column(Text)
    code = Column(Text)
    city = Column(Text)
    state = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Course(Base):
    __tablename__ = "courses"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    campus_id = Column(UUID(as_uuid=True), ForeignKey("campus.id"))
    course_name = Column(Text)
    course_code = Column(Text)
    shift = Column(Text)
    modality = Column(Text)
    degree = Column(Text)
    scholarship_type = Column(Text)
    grade = Column(Float)
    min_grade = Column(Float)
    max_grade = Column(Float)
    vacancies = Column(Integer)
    concurrency_tag = Column(Text)
    source = Column(Text)
    year = Column(Integer)
    occupied = Column(JSONB, server_default=sa_text("'[]'::jsonb"))
    vagas_ociosas_2025 = Column(JSONB, server_default=sa_text("'[]'::jsonb"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class InstitutionInfoEmec(Base):
    __tablename__ = "institutions_info_emec"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    co_ies = Column(Text)
    no_ies = Column(Text)
    sigla = Column(Text)
    categoria = Column(Text)
    natureza = Column(Text)
    cidade = Column(Text)
    uf = Column(Text)
    igc_continuo = Column(Float)
    igc_faixa = Column(Text)
    ci_continuo = Column(Float)
    ci_faixa = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# Sisu Vacancies
# ============================================================

class OpportunitySisuVacancy(Base):
    __tablename__ = "opportunities_sisu_vacancies"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"))
    year = Column(Integer)
    edition = Column(Integer)
    modality = Column(Text)
    vacancies = Column(Integer)
    min_grade = Column(Float)
    max_grade = Column(Float)
    avg_grade = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# User Domain
# ============================================================

class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True)
    full_name = Column(Text)
    age = Column(Integer)
    city = Column(Text)
    state = Column(Text)
    education = Column(Text)
    interests = Column(Text)
    onboarding_completed = Column(Boolean, server_default=sa_text("false"))
    active_workflow = Column(Text)
    is_nubo_student = Column(Boolean, server_default=sa_text("false"))
    referral_source = Column(Text)
    workflow_data = Column(JSONB, server_default=sa_text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_profiles.id"), unique=True, nullable=False)
    course_interest = Column(ARRAY(Text))
    location_preference = Column(Text)
    max_distance_km = Column(Integer)
    latitude = Column(Float)
    longitude = Column(Float)
    modality_preference = Column(Text)
    shift_preference = Column(Text)
    scholarship_type = Column(Text)
    enem_score = Column(Float)
    family_income_per_capita = Column(Float)
    quota_types = Column(ARRAY(Text))
    registration_step = Column(Text, server_default=sa_text("'intro'"))
    workflow_data = Column(JSONB, server_default=sa_text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class UserEnemScore(Base):
    __tablename__ = "user_enem_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_profiles.id"), nullable=False)
    year = Column(Integer, nullable=False)
    linguagens = Column(Float)
    matematica = Column(Float)
    ciencias_natureza = Column(Float)
    ciencias_humanas = Column(Float)
    redacao = Column(Float)
    media_objetiva = Column(Float)
    media_total = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "year", name="uq_user_enem_scores_user_year"),
    )


class UserFavorite(Base):
    __tablename__ = "user_favorites"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_profiles.id"), nullable=False)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "course_id", name="uq_user_favorites_user_course"),
    )


# ============================================================
# Chat & Agent
# ============================================================

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True))
    session_id = Column(Text)
    role = Column(Text, nullable=False)
    content = Column(Text)
    metadata_ = Column("metadata", JSONB)
    workflow = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ModerationLog(Base):
    __tablename__ = "moderation_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True))
    session_id = Column(Text)
    message_content = Column(Text)
    moderation_result = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AgentError(Base):
    __tablename__ = "agent_errors"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True))
    session_id = Column(Text)
    error_type = Column(Text)
    error_message = Column(Text)
    stack_trace = Column(Text)
    metadata_ = Column("metadata", JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AgentExecution(Base):
    __tablename__ = "agent_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True))
    session_id = Column(Text)
    workflow = Column(Text)
    tool_name = Column(Text)
    tool_input = Column(JSONB)
    tool_output = Column(JSONB)
    duration_ms = Column(Integer)
    success = Column(Boolean)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Document(Base):
    """RAG documents for knowledge base."""
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    content = Column(Text)
    metadata_ = Column("metadata", JSONB)
    # embedding column is managed by pgvector extension, not SQLAlchemy
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AgentFeedback(Base):
    __tablename__ = "agent_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True))
    session_id = Column(Text)
    question = Column(Text)
    answer = Column(Text)
    was_helpful = Column(Boolean)
    feedback_text = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# Partners & Applications
# ============================================================

class Partner(Base):
    __tablename__ = "partners"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    name = Column(Text)
    description = Column(Text)
    location = Column(Text)
    type = Column(Text)
    income = Column(Text)
    dates = Column(JSONB)
    link = Column(Text)
    coverimage = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class PartnerStep(Base):
    __tablename__ = "partner_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    partner_id = Column(UUID(as_uuid=True), ForeignKey("partners.id"), nullable=False)
    step_name = Column(Text, nullable=False)
    sort_order = Column(Integer, nullable=False, server_default=sa_text("0"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class PartnerForm(Base):
    __tablename__ = "partner_forms"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    partner_id = Column(UUID(as_uuid=True), ForeignKey("partners.id"), nullable=False)
    field_name = Column(Text, nullable=False)
    question_text = Column(Text, nullable=False)
    data_type = Column(Text, nullable=False, server_default=sa_text("'text'"))
    options = Column(JSONB)
    mapping_source = Column(Text)
    is_criterion = Column(Boolean, nullable=False, server_default=sa_text("false"))
    criterion_rule = Column(JSONB)
    sort_order = Column(Integer, nullable=False, server_default=sa_text("0"))
    step_id = Column(UUID(as_uuid=True), ForeignKey("partner_steps.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class PartnersUser(Base):
    __tablename__ = "partners_users"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False)
    partner_id = Column(UUID(as_uuid=True), ForeignKey("partners.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "partner_id", name="uq_partners_users"),
    )


class PartnerSolicitation(Base):
    __tablename__ = "partner_solicitations"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    partner_id = Column(UUID(as_uuid=True), ForeignKey("partners.id"))
    user_id = Column(UUID(as_uuid=True))
    status = Column(Text, server_default=sa_text("'pending'"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PartnerClick(Base):
    __tablename__ = "partners_click"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    partner_id = Column(UUID(as_uuid=True), ForeignKey("partners.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True))
    click_type = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class StudentApplication(Base):
    __tablename__ = "student_applications"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False)
    partner_id = Column(UUID(as_uuid=True), ForeignKey("partners.id"), nullable=False)
    status = Column(Text, nullable=False, server_default=sa_text("'started'"))
    answers = Column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# Influencers
# ============================================================

class Influencer(Base):
    __tablename__ = "influencers"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    name = Column(Text, nullable=False)
    code = Column(Text, unique=True, nullable=False)
    active = Column(Boolean, server_default=sa_text("true"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# Sean Ellis Score
# ============================================================

class SeanEllisScore(Base):
    __tablename__ = "sean_ellis_score"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    submitted_at = Column(DateTime(timezone=True))
    full_name = Column(Text)
    whatsapp_raw = Column(Text)
    whatsapp_normalized = Column(Text)
    sisu_subscribed = Column(Text)
    sisu_courses = Column(Text)
    sisu_status = Column(Text)
    sisu_cloudinha_influence = Column(Text)
    prouni_subscribed = Column(Text)
    prouni_courses = Column(Text)
    prouni_cloudinha_influence = Column(Text)
    prouni_status = Column(Text)
    disappointment_level = Column(Text)
    feedback = Column(Text)
    user_id = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# AI & Analytics
# ============================================================

class AIInsight(Base):
    __tablename__ = "ai_insights"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    insights = Column(JSONB, nullable=False)
    data_context = Column(JSONB, nullable=False)
    data_hash = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


# ============================================================
# Permissions & Rate Limiting
# ============================================================

class UserPermission(Base):
    __tablename__ = "user_permissions"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False)
    permission = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "permission", name="uq_user_permissions"),
    )


class UserRateLimit(Base):
    __tablename__ = "user_rate_limits"

    user_id = Column(UUID(as_uuid=True), primary_key=True)
    last_message_at = Column(DateTime(timezone=True), server_default=func.now())
    message_count_window = Column(Integer, server_default=sa_text("0"))


# ============================================================
# Whitelist & Import Tables
# ============================================================

class NuboStudentWhitelist(Base):
    __tablename__ = "nubo_student_whitelist"

    phone_number = Column(Text, primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# Important Dates
# ============================================================

class ImportantDate(Base):
    __tablename__ = "important_dates"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    title = Column(Text, nullable=False)
    description = Column(Text)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True))
    type = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# Opportunities (Match Engine)
# ============================================================

class Opportunity(Base):
    __tablename__ = "opportunities"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"))
    source = Column(Text)
    year = Column(Integer)
    shift = Column(Text)
    modality = Column(Text)
    scholarship_type = Column(Text)
    grade = Column(Float)
    min_grade = Column(Float)
    max_grade = Column(Float)
    vacancies = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# Passport (Workflow)
# ============================================================

class PassportApplication(Base):
    __tablename__ = "passport_applications"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_profiles.id"), nullable=False)
    partner_id = Column(UUID(as_uuid=True), ForeignKey("partners.id"), nullable=False)
    status = Column(Text, nullable=False, server_default=sa_text("'pending'"))
    eligible = Column(Boolean)
    eligibility_details = Column(JSONB)
    submitted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

