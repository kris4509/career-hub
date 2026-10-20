import re

from flask import Blueprint, current_app, request, jsonify
from flask_jwt_extended import get_jwt_identity

from ..extensions import db
from ..models import Application, User, utcnow
from ..routes.jobs import get_or_create_skills
from ..utils import storage
from ..utils.decorators import roles_required

profiles_bp = Blueprint("profiles", __name__, url_prefix="/api")

AVAILABILITY = {"full-time", "part-time", "contract"}
EDUCATION = {"secondary", "certificate", "diploma", "bachelors", "masters", "doctorate", "other"}
PHONE_RE = re.compile(r"^\+?[0-9][0-9 ()\-]{6,28}$")

# (field, label for error messages, maximum length)
TEXT_FIELDS = [("headline", "Headline", 200), ("bio", "Bio", 2000), ("location", "Location", 150)]
URL_FIELDS = [("resume_url", "Resume link", 500), ("linkedin_url", "LinkedIn link", 300), ("portfolio_url", "Portfolio link", 300)]


def completeness(profile):
    checks = [
        ("full name", bool(profile.full_name)),
        ("headline", bool(profile.headline)),
        ("phone number", bool(profile.phone)),
        ("location", bool(profile.location)),
        ("education", bool(profile.education)),
        ("availability", bool(profile.availability)),
        ("skills", len(profile.skills) > 0),
        ("short bio", bool(profile.bio)),
        ("CV", bool(profile.resume_path or profile.resume_url)),
    ]
    done = sum(1 for _, ok in checks if ok)
    return {
        "percent": round(done * 100 / len(checks)),
        "missing": [name for name, ok in checks if not ok],
    }


def candidate_to_dict(profile):
    return {
        "id": profile.id,
        "email": profile.user.email,
        "full_name": profile.full_name,
        "headline": profile.headline,
        "bio": profile.bio,
        "location": profile.location,
        "phone": profile.phone,
        "education": profile.education,
        "experience_years": profile.experience_years,
        "availability": profile.availability,
        "resume_url": profile.resume_url,
        "linkedin_url": profile.linkedin_url,
        "portfolio_url": profile.portfolio_url,
        "has_resume": bool(profile.resume_path),
        "resume_filename": profile.resume_filename,
        "resume_uploaded_at": profile.resume_uploaded_at.isoformat() if profile.resume_uploaded_at else None,
        "skills": [s.name for s in profile.skills],
        "completeness": completeness(profile),
    }


def current_candidate():
    user = db.session.get(User, int(get_jwt_identity()))
    return user.candidate_profile if user else None


def read_text(data, field, label, max_len):
    """Returns (value, error). Empty text becomes None."""
    value = data.get(field)
    if value is None:
        return None, None
    if not isinstance(value, str):
        return None, f"{label} must be text"
    value = value.strip()
    if len(value) > max_len:
        return None, f"{label} is too long (maximum {max_len} characters)"
    return (value or None), None


def storage_failed(err):
    current_app.logger.error("Storage problem: %s", err)
    return jsonify({"error": "File storage is not available right now. Please try again in a moment."}), 502


@profiles_bp.app_errorhandler(413)
def too_large(_err):
    return jsonify({"error": "That file is too large. The limit is 8 MB."}), 413


# ---------- Candidate profile ----------

@profiles_bp.route("/profile/candidate", methods=["GET"])
@roles_required("candidate")
def get_my_profile():
    profile = current_candidate()
    if not profile:
        return jsonify({"error": "Candidate profile not found"}), 404
    return jsonify({"profile": candidate_to_dict(profile)})


@profiles_bp.route("/profile/candidate", methods=["PUT"])
@roles_required("candidate")
def update_my_profile():
    """Updates only the fields you send; fields you leave out stay as they are."""
    profile = current_candidate()
    if not profile:
        return jsonify({"error": "Candidate profile not found"}), 404

    data = request.get_json(silent=True) or {}

    if "full_name" in data:
        value, error = read_text(data, "full_name", "Full name", 150)
        if error:
            return jsonify({"error": error}), 400
        if not value:
            return jsonify({"error": "Full name cannot be empty"}), 400
        profile.full_name = value

    for field, label, max_len in TEXT_FIELDS:
        if field in data:
            value, error = read_text(data, field, label, max_len)
            if error:
                return jsonify({"error": error}), 400
            setattr(profile, field, value)

    if "phone" in data:
        value, error = read_text(data, "phone", "Phone number", 30)
        if error:
            return jsonify({"error": error}), 400
        if value and not PHONE_RE.match(value):
            return jsonify({"error": "Enter a valid phone number, for example +254 700 000000"}), 400
        profile.phone = value

    if "education" in data:
        value = data["education"]
        if value in (None, ""):
            profile.education = None
        elif value in EDUCATION:
            profile.education = value
        else:
            return jsonify({"error": f"education must be one of {sorted(EDUCATION)}"}), 400

    if "experience_years" in data:
        years = data["experience_years"]
        if not isinstance(years, int) or isinstance(years, bool) or years < 0 or years > 60:
            return jsonify({"error": "experience_years must be a whole number from 0 to 60"}), 400
        profile.experience_years = years

    if "availability" in data:
        value = data["availability"]
        if value in (None, ""):
            profile.availability = None
        elif value in AVAILABILITY:
            profile.availability = value
        else:
            return jsonify({"error": f"availability must be one of {sorted(AVAILABILITY)}"}), 400

    for field, label, max_len in URL_FIELDS:
        if field in data:
            value, error = read_text(data, field, label, max_len)
            if error:
                return jsonify({"error": error}), 400
            if value and not value.lower().startswith(("http://", "https://")):
                return jsonify({"error": f"{label} must start with http:// or https://"}), 400
            setattr(profile, field, value)

    if "skills" in data:
        names = data["skills"]
        if not isinstance(names, list) or len(names) > 30:
            return jsonify({"error": "skills must be a list of up to 30 names"}), 400
        if any(not isinstance(n, str) or len(n.strip()) > 50 for n in names):
            return jsonify({"error": "Each skill must be text of 50 characters or fewer"}), 400
        profile.skills = get_or_create_skills(names)

    db.session.commit()
    return jsonify({"profile": candidate_to_dict(profile)})


# ---------- CV file ----------

@profiles_bp.route("/profile/candidate/resume", methods=["POST"])
@roles_required("candidate")
def upload_my_resume():
    profile = current_candidate()
    if not profile:
        return jsonify({"error": "Candidate profile not found"}), 404

    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "Please choose a file."}), 400

    data = file.read(storage.MAX_RESUME_BYTES + 1)

    try:
        new_path, display_name = storage.upload_resume(profile.id, file.filename, data)
    except ValueError as err:
        return jsonify({"error": str(err)}), 400
    except storage.StorageError as err:
        return storage_failed(err)

    old_path = profile.resume_path
    try:
        profile.resume_path = new_path
        profile.resume_filename = display_name
        profile.resume_uploaded_at = utcnow()
        db.session.commit()
    except Exception:
        # The database save failed, so don't leave an orphan file behind
        db.session.rollback()
        try:
            storage.delete_file(new_path)
        except storage.StorageError:
            pass
        raise

    # Replace the old CV only after the new one is safely saved
    if old_path:
        try:
            storage.delete_file(old_path)
        except storage.StorageError as err:
            current_app.logger.warning("Could not delete old CV %s: %s", old_path, err)

    return jsonify({"profile": candidate_to_dict(profile)}), 201


@profiles_bp.route("/profile/candidate/resume", methods=["DELETE"])
@roles_required("candidate")
def delete_my_resume():
    profile = current_candidate()
    if not profile:
        return jsonify({"error": "Candidate profile not found"}), 404
    if not profile.resume_path:
        return jsonify({"error": "You have not uploaded a CV."}), 404

    path = profile.resume_path
    profile.resume_path = None
    profile.resume_filename = None
    profile.resume_uploaded_at = None
    db.session.commit()

    try:
        storage.delete_file(path)
    except storage.StorageError as err:
        current_app.logger.warning("Could not delete CV %s: %s", path, err)

    return jsonify({"profile": candidate_to_dict(profile)})


@profiles_bp.route("/profile/candidate/resume/link", methods=["GET"])
@roles_required("candidate")
def my_resume_link():
    """A temporary link to my own CV (works for 5 minutes)."""
    profile = current_candidate()
    if not profile or not profile.resume_path:
        return jsonify({"error": "You have not uploaded a CV."}), 404
    try:
        url = storage.signed_url(profile.resume_path, expires=300)
    except storage.StorageError as err:
        return storage_failed(err)
    return jsonify({"url": url, "filename": profile.resume_filename, "expires_in": 300})


# ---------- Employer view of an applicant's CV ----------

@profiles_bp.route("/applications/<int:application_id>/resume", methods=["GET"])
@roles_required("employer", "admin")
def applicant_resume_link(application_id):
    """A temporary link to the CV of someone who applied to one of MY jobs."""
    user = db.session.get(User, int(get_jwt_identity()))
    application = db.session.get(Application, application_id)
    if not user or not application:
        return jsonify({"error": "Application not found"}), 404

    if user.role == "employer":
        if not user.employer_profile or application.job.employer_id != user.employer_profile.id:
            return jsonify({"error": "Application not found"}), 404

    candidate = application.candidate
    if not candidate.resume_path:
        return jsonify({"error": "This applicant has not uploaded a CV file."}), 404

    try:
        url = storage.signed_url(candidate.resume_path, expires=300)
    except storage.StorageError as err:
        return storage_failed(err)
    return jsonify({"url": url, "filename": candidate.resume_filename, "expires_in": 300})