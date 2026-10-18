from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request
from sqlalchemy import or_

from ..extensions import db
from ..models import Job, Skill, User
from ..utils.decorators import roles_required

jobs_bp = Blueprint("jobs", __name__, url_prefix="/api/jobs")

WORK_MODES = {"remote", "onsite", "hybrid"}
JOB_TYPES = {"full-time", "part-time", "contract"}


def job_to_dict(job):
    return {
        "id": job.id,
        "title": job.title,
        "description": job.description,
        "location": job.location,
        "work_mode": job.work_mode,
        "job_type": job.job_type,
        "pay_min": job.pay_min,
        "pay_max": job.pay_max,
        "currency": job.currency,
        "status": job.status,
        "skills": [s.name for s in job.skills],
        "company": job.employer.company_name,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


def get_or_create_skills(names):
    skills = []
    for raw in names:
        name = str(raw).strip()
        if not name:
            continue
        skill = Skill.query.filter(db.func.lower(Skill.name) == name.lower()).first()
        if not skill:
            skill = Skill(name=name)
            db.session.add(skill)
        if skill not in skills:
            skills.append(skill)
    return skills


@jobs_bp.route("", methods=["GET"])
def list_jobs():
    """Public: list open jobs, with optional search and filters."""
    q = (request.args.get("q") or "").strip()
    location = (request.args.get("location") or "").strip()
    work_mode = request.args.get("work_mode")
    job_type = request.args.get("job_type")
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 10, type=int), 1), 50)

    query = Job.query.filter_by(status="open")
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Job.title.ilike(like), Job.description.ilike(like)))
    if location:
        query = query.filter(Job.location.ilike(f"%{location}%"))
    if work_mode in WORK_MODES:
        query = query.filter_by(work_mode=work_mode)
    if job_type in JOB_TYPES:
        query = query.filter_by(job_type=job_type)

    result = query.order_by(Job.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify(
        {
            "jobs": [job_to_dict(j) for j in result.items],
            "page": result.page,
            "pages": result.pages,
            "total": result.total,
        }
    )


@jobs_bp.route("/<int:job_id>", methods=["GET"])
def get_job(job_id):
    """Public for open jobs. Pending/closed jobs are visible only to their owner or an admin."""
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.status != "open":
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        allowed = False
        if identity:
            user = db.session.get(User, int(identity))
            if user and (
                user.role == "admin"
                or (user.employer_profile and user.employer_profile.id == job.employer_id)
            ):
                allowed = True
        if not allowed:
            return jsonify({"error": "Job not found"}), 404

    return jsonify({"job": job_to_dict(job)})


@jobs_bp.route("", methods=["POST"])
@roles_required("employer")
def create_job():
    """Employers only. New jobs start as 'pending' until an admin approves them."""
    user = db.session.get(User, int(get_jwt_identity()))
    if not user or not user.employer_profile:
        return jsonify({"error": "Employer profile not found"}), 404

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    work_mode = data.get("work_mode", "remote")
    job_type = data.get("job_type", "full-time")
    pay_min = data.get("pay_min")
    pay_max = data.get("pay_max")

    if not title:
        return jsonify({"error": "Title is required"}), 400
    if not description:
        return jsonify({"error": "Description is required"}), 400
    if work_mode not in WORK_MODES:
        return jsonify({"error": f"work_mode must be one of {sorted(WORK_MODES)}"}), 400
    if job_type not in JOB_TYPES:
        return jsonify({"error": f"job_type must be one of {sorted(JOB_TYPES)}"}), 400
    for value in (pay_min, pay_max):
        if value is not None and (not isinstance(value, int) or value < 0):
            return jsonify({"error": "pay_min and pay_max must be whole numbers, 0 or more"}), 400
    if pay_min is not None and pay_max is not None and pay_min > pay_max:
        return jsonify({"error": "pay_min cannot be greater than pay_max"}), 400

    skill_names = data.get("skills") or []
    if not isinstance(skill_names, list):
        return jsonify({"error": "skills must be a list of names"}), 400

    job = Job(
        employer_id=user.employer_profile.id,
        title=title,
        description=description,
        location=(data.get("location") or "").strip() or None,
        work_mode=work_mode,
        job_type=job_type,
        pay_min=pay_min,
        pay_max=pay_max,
        currency=(data.get("currency") or "KES").strip().upper(),
        status="pending",
    )
    job.skills = get_or_create_skills(skill_names)
    db.session.add(job)
    db.session.commit()

    return jsonify({"job": job_to_dict(job)}), 201


@jobs_bp.route("/mine", methods=["GET"])
@roles_required("employer")
def my_jobs():
    """Employers only: all of my own jobs, whatever their status."""
    user = db.session.get(User, int(get_jwt_identity()))
    if not user or not user.employer_profile:
        return jsonify({"error": "Employer profile not found"}), 404

    jobs = (
        Job.query.filter_by(employer_id=user.employer_profile.id)
        .order_by(Job.created_at.desc())
        .all()
    )
    return jsonify({"jobs": [job_to_dict(j) for j in jobs]})