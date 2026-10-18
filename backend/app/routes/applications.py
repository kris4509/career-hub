from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Application, Job, User
from ..utils.decorators import roles_required

applications_bp = Blueprint("applications", __name__, url_prefix="/api")

STATUSES = {"applied", "shortlisted", "accepted", "rejected"}


def application_to_dict(app_obj, include_candidate=False):
    data = {
        "id": app_obj.id,
        "job_id": app_obj.job_id,
        "job_title": app_obj.job.title,
        "company": app_obj.job.employer.company_name,
        "status": app_obj.status,
        "cover_letter": app_obj.cover_letter,
        "created_at": app_obj.created_at.isoformat() if app_obj.created_at else None,
    }
    if include_candidate:
        c = app_obj.candidate
        data["candidate"] = {
            "id": c.id,
            "full_name": c.full_name,
            "email": c.user.email,
            "headline": c.headline,
            "location": c.location,
            "experience_years": c.experience_years,
            "availability": c.availability,
            "resume_url": c.resume_url,
            "skills": [s.name for s in c.skills],
        }
    return data


@applications_bp.route("/jobs/<int:job_id>/apply", methods=["POST"])
@roles_required("candidate")
def apply_to_job(job_id):
    """Candidates only: apply to an open job (once per job)."""
    user = db.session.get(User, int(get_jwt_identity()))
    if not user or not user.candidate_profile:
        return jsonify({"error": "Candidate profile not found"}), 404

    job = db.session.get(Job, job_id)
    if not job or job.status != "open":
        return jsonify({"error": "Job not found or not open for applications"}), 404

    existing = Application.query.filter_by(
        job_id=job.id, candidate_id=user.candidate_profile.id
    ).first()
    if existing:
        return jsonify({"error": "You have already applied to this job"}), 409

    data = request.get_json(silent=True) or {}
    application = Application(
        job_id=job.id,
        candidate_id=user.candidate_profile.id,
        cover_letter=(data.get("cover_letter") or "").strip() or None,
        status="applied",
    )
    db.session.add(application)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "You have already applied to this job"}), 409

    return jsonify({"application": application_to_dict(application)}), 201


@applications_bp.route("/applications/mine", methods=["GET"])
@roles_required("candidate")
def my_applications():
    """Candidates only: every job I've applied to, with its status."""
    user = db.session.get(User, int(get_jwt_identity()))
    if not user or not user.candidate_profile:
        return jsonify({"error": "Candidate profile not found"}), 404

    apps = (
        Application.query.filter_by(candidate_id=user.candidate_profile.id)
        .order_by(Application.created_at.desc())
        .all()
    )
    return jsonify({"applications": [application_to_dict(a) for a in apps]})


@applications_bp.route("/jobs/<int:job_id>/applications", methods=["GET"])
@roles_required("employer")
def job_applicants(job_id):
    """Employers only: applicants for one of MY jobs."""
    user = db.session.get(User, int(get_jwt_identity()))
    job = db.session.get(Job, job_id)
    if not user or not user.employer_profile or not job or job.employer_id != user.employer_profile.id:
        return jsonify({"error": "Job not found"}), 404

    apps = Application.query.filter_by(job_id=job.id).order_by(Application.created_at.desc()).all()
    return jsonify({"applications": [application_to_dict(a, include_candidate=True) for a in apps]})


@applications_bp.route("/applications/<int:application_id>", methods=["PATCH"])
@roles_required("employer")
def update_application(application_id):
    """Employers only: change the status of an applicant on one of MY jobs."""
    user = db.session.get(User, int(get_jwt_identity()))
    application = db.session.get(Application, application_id)
    if (
        not user
        or not user.employer_profile
        or not application
        or application.job.employer_id != user.employer_profile.id
    ):
        return jsonify({"error": "Application not found"}), 404

    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in STATUSES:
        return jsonify({"error": f"status must be one of {sorted(STATUSES)}"}), 400

    application.status = status
    db.session.commit()
    return jsonify({"application": application_to_dict(application, include_candidate=True)})