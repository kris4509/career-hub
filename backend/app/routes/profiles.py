from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity

from ..extensions import db
from ..models import User
from ..routes.jobs import get_or_create_skills
from ..utils.decorators import roles_required

profiles_bp = Blueprint("profiles", __name__, url_prefix="/api/profile")

AVAILABILITY = {"full-time", "part-time", "contract"}


def candidate_to_dict(profile):
    return {
        "id": profile.id,
        "email": profile.user.email,
        "full_name": profile.full_name,
        "headline": profile.headline,
        "bio": profile.bio,
        "location": profile.location,
        "experience_years": profile.experience_years,
        "availability": profile.availability,
        "resume_url": profile.resume_url,
        "skills": [s.name for s in profile.skills],
    }


def current_candidate():
    user = db.session.get(User, int(get_jwt_identity()))
    return user.candidate_profile if user else None


@profiles_bp.route("/candidate", methods=["GET"])
@roles_required("candidate")
def get_my_profile():
    profile = current_candidate()
    if not profile:
        return jsonify({"error": "Candidate profile not found"}), 404
    return jsonify({"profile": candidate_to_dict(profile)})


@profiles_bp.route("/candidate", methods=["PUT"])
@roles_required("candidate")
def update_my_profile():
    """Updates only the fields you send; fields you leave out stay as they are."""
    profile = current_candidate()
    if not profile:
        return jsonify({"error": "Candidate profile not found"}), 404

    data = request.get_json(silent=True) or {}

    if "full_name" in data:
        name = (data["full_name"] or "").strip()
        if not name:
            return jsonify({"error": "full_name cannot be empty"}), 400
        profile.full_name = name

    for field in ("headline", "bio", "location"):
        if field in data:
            profile_value = (data[field] or "").strip()
            setattr(profile, field, profile_value or None)

    if "experience_years" in data:
        years = data["experience_years"]
        if not isinstance(years, int) or isinstance(years, bool) or years < 0 or years > 60:
            return jsonify({"error": "experience_years must be a whole number from 0 to 60"}), 400
        profile.experience_years = years

    if "availability" in data:
        if data["availability"] not in AVAILABILITY:
            return jsonify({"error": f"availability must be one of {sorted(AVAILABILITY)}"}), 400
        profile.availability = data["availability"]

    if "resume_url" in data:
        url = (data["resume_url"] or "").strip()
        if url and not url.lower().startswith(("http://", "https://")):
            return jsonify({"error": "resume_url must start with http:// or https://"}), 400
        profile.resume_url = url or None

    if "skills" in data:
        names = data["skills"]
        if not isinstance(names, list) or len(names) > 30:
            return jsonify({"error": "skills must be a list of up to 30 names"}), 400
        profile.skills = get_or_create_skills(names)

    db.session.commit()
    return jsonify({"profile": candidate_to_dict(profile)})