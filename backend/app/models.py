from datetime import datetime, timezone

from werkzeug.security import generate_password_hash, check_password_hash

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc)


# Many-to-many link tables
candidate_skills = db.Table(
    "candidate_skills",
    db.Column("candidate_id", db.Integer, db.ForeignKey("candidate_profiles.id", ondelete="CASCADE"), primary_key=True),
    db.Column("skill_id", db.Integer, db.ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
)

job_skills = db.Table(
    "job_skills",
    db.Column("job_id", db.Integer, db.ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True),
    db.Column("skill_id", db.Integer, db.ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="candidate")  # candidate / employer / admin
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    candidate_profile = db.relationship(
        "CandidateProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    employer_profile = db.relationship(
        "EmployerProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Skill(db.Model):
    __tablename__ = "skills"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)


class CandidateProfile(db.Model):
    __tablename__ = "candidate_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    headline = db.Column(db.String(200))
    bio = db.Column(db.Text)
    location = db.Column(db.String(150))
    experience_years = db.Column(db.Integer, default=0)
    availability = db.Column(db.String(50))  # e.g. full-time, part-time, contract
    resume_url = db.Column(db.String(500))  # optional link (Drive, LinkedIn...)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    # Added for onboarding
    phone = db.Column(db.String(30))
    education = db.Column(db.String(50))
    linkedin_url = db.Column(db.String(300))
    portfolio_url = db.Column(db.String(300))
    resume_path = db.Column(db.String(300))  # file path inside the private bucket
    resume_filename = db.Column(db.String(200))  # original file name, for display
    resume_uploaded_at = db.Column(db.DateTime(timezone=True))
    date_of_birth = db.Column(db.Date)

    user = db.relationship("User", back_populates="candidate_profile")
    skills = db.relationship("Skill", secondary=candidate_skills, backref="candidates")
    applications = db.relationship("Application", back_populates="candidate", cascade="all, delete-orphan")


class EmployerProfile(db.Model):
    __tablename__ = "employer_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    company_name = db.Column(db.String(200), nullable=False)
    website = db.Column(db.String(300))
    description = db.Column(db.Text)
    location = db.Column(db.String(150))
    is_approved = db.Column(db.Boolean, nullable=False, default=False)  # admin approves employers
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    user = db.relationship("User", back_populates="employer_profile")
    jobs = db.relationship("Job", back_populates="employer", cascade="all, delete-orphan")


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.Integer, primary_key=True)
    employer_id = db.Column(db.Integer, db.ForeignKey("employer_profiles.id", ondelete="CASCADE"), nullable=False)
    title = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(150))
    work_mode = db.Column(db.String(30), default="remote")  # remote / onsite / hybrid
    job_type = db.Column(db.String(30), default="full-time")  # full-time / part-time / contract
    pay_min = db.Column(db.Integer)
    pay_max = db.Column(db.Integer)
    currency = db.Column(db.String(10), default="KES")
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending / open / closed
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    employer = db.relationship("EmployerProfile", back_populates="jobs")
    skills = db.relationship("Skill", secondary=job_skills, backref="jobs")
    applications = db.relationship("Application", back_populates="job", cascade="all, delete-orphan")


class Application(db.Model):
    __tablename__ = "applications"
    __table_args__ = (db.UniqueConstraint("job_id", "candidate_id", name="uq_application_job_candidate"),)

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    candidate_id = db.Column(db.Integer, db.ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False)
    cover_letter = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default="applied")  # applied / shortlisted / accepted / rejected
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    job = db.relationship("Job", back_populates="applications")
    candidate = db.relationship("CandidateProfile", back_populates="applications")