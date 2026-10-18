from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity

from ..extensions import db
from ..models import EmployerProfile, Job, User
from ..routes.jobs import job_to_dict
from ..utils.decorators import roles_required

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def employer_to_dict(emp):
    return {
        "id": emp.id,
        "company_name": emp.company_name,
        "website": emp.website,
        "location": emp.location,
        "email": emp.user.email,
        "is_approved": emp.is_approved,
        "created_at": emp.created_at.isoformat() if emp.created_at else None,
    }


def admin_user_to_dict(user):
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@admin_bp.route("/employers", methods=["GET"])
@roles_required("admin")
def list_employers():
    """Optional filter: ?approved=true or ?approved=false"""
    query = EmployerProfile.query
    approved = request.args.get("approved")
    if approved in ("true", "false"):
        query = query.filter_by(is_approved=(approved == "true"))
    employers = query.order_by(EmployerProfile.created_at.desc()).all()
    return jsonify({"employers": [employer_to_dict(e) for e in employers]})


@admin_bp.route("/employers/<int:employer_id>", methods=["PATCH"])
@roles_required("admin")
def set_employer_approval(employer_id):
    emp = db.session.get(EmployerProfile, employer_id)
    if not emp:
        return jsonify({"error": "Employer not found"}), 404

    data = request.get_json(silent=True) or {}
    if not isinstance(data.get("is_approved"), bool):
        return jsonify({"error": "is_approved must be true or false"}), 400

    emp.is_approved = data["is_approved"]
    db.session.commit()
    return jsonify({"employer": employer_to_dict(emp)})


@admin_bp.route("/jobs", methods=["GET"])
@roles_required("admin")
def list_jobs():
    """Optional filter: ?status=pending (or open / closed)"""
    query = Job.query
    status = request.args.get("status")
    if status in ("pending", "open", "closed"):
        query = query.filter_by(status=status)
    jobs = query.order_by(Job.created_at.desc()).all()
    return jsonify({"jobs": [job_to_dict(j) for j in jobs]})


@admin_bp.route("/jobs/<int:job_id>", methods=["PATCH"])
@roles_required("admin")
def set_job_status(job_id):
    """Approve a job (status 'open') or reject/close it (status 'closed')."""
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in ("open", "closed"):
        return jsonify({"error": "status must be 'open' or 'closed'"}), 400
    if status == "open" and not job.employer.is_approved:
        return jsonify({"error": "Approve the employer before approving their jobs"}), 400

    job.status = status
    db.session.commit()
    return jsonify({"job": job_to_dict(job)})


@admin_bp.route("/users", methods=["GET"])
@roles_required("admin")
def list_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify({"users": [admin_user_to_dict(u) for u in users]})


@admin_bp.route("/users/<int:user_id>", methods=["PATCH"])
@roles_required("admin")
def set_user_active(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    if user.id == int(get_jwt_identity()):
        return jsonify({"error": "You cannot disable your own account"}), 400

    data = request.get_json(silent=True) or {}
    if not isinstance(data.get("is_active"), bool):
        return jsonify({"error": "is_active must be true or false"}), 400

    user.is_active = data["is_active"]
    db.session.commit()
    return jsonify({"user": admin_user_to_dict(user)})