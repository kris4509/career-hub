from functools import wraps

from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt


def roles_required(*allowed_roles):
    """Allow a route only for logged-in users whose role is in allowed_roles.

    Usage:
        @jobs_bp.route("/", methods=["POST"])
        @roles_required("employer")
        def create_job(): ...
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()  # 401 if the token is missing or invalid
            claims = get_jwt()
            if claims.get("role") not in allowed_roles:
                return jsonify({"error": "You do not have permission to do this"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator