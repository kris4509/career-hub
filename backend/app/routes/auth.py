from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

from ..extensions import db
from ..models import User, CandidateProfile, EmployerProfile

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

ALLOWED_SIGNUP_ROLES = {"candidate", "employer"}  # admins are never created through the API


def user_to_dict(user):
    data = {"id": user.id, "email": user.email, "role": user.role}
    if user.role == "candidate" and user.candidate_profile:
        data["name"] = user.candidate_profile.full_name
    elif user.role == "employer" and user.employer_profile:
        data["name"] = user.employer_profile.company_name
        data["is_approved"] = user.employer_profile.is_approved
    return data


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = data.get("role")
    name = (data.get("name") or "").strip()  # full name or company name

    if not email or "@" not in email:
        return jsonify({"error": "A valid email is required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    if role not in ALLOWED_SIGNUP_ROLES:
        return jsonify({"error": "Role must be 'candidate' or 'employer'"}), 400
    if not name:
        return jsonify({"error": "Name is required (full name or company name)"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "That email is already registered"}), 409

    user = User(email=email, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()  # gives user.id before commit

    if role == "candidate":
        db.session.add(CandidateProfile(user_id=user.id, full_name=name))
    else:
        db.session.add(EmployerProfile(user_id=user.id, company_name=name))

    db.session.commit()

    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    return jsonify({"access_token": token, "user": user_to_dict(user)}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password"}), 401
    if not user.is_active:
        return jsonify({"error": "This account has been disabled"}), 403

    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    return jsonify({"access_token": token, "user": user_to_dict(user)})


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user = db.session.get(User, int(get_jwt_identity()))
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"user": user_to_dict(user)})