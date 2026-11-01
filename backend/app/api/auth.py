import re

from flask import Blueprint, jsonify
from flask_jwt_extended import create_access_token
from sqlalchemy import or_

from ..constants import ROLE_OPERATOR, ROLES
from ..errors import ApiError
from ..extensions import db
from ..models import User
from ..security import current_user, login_required, roles_required
from ..utils import json_body, require_fields

bp = Blueprint("auth", __name__)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@bp.post("/auth/register")
def register():
    data = json_body()
    require_fields(data, "username", "email", "password")
    username, email = str(data["username"]).strip(), str(data["email"]).strip().lower()
    if not (3 <= len(username) <= 50):
        raise ApiError("Username must be 3-50 characters")
    if not EMAIL_RE.match(email):
        raise ApiError("Invalid email")
    if len(str(data["password"])) < 8:
        raise ApiError("Password must be at least 8 characters")
    if User.query.filter(or_(User.username == username, User.email == email)).first():
        raise ApiError("Username or email already exists", 409)
    user = User(username=username, email=email, role=ROLE_OPERATOR)  # self-register hamesha operator
    user.set_password(str(data["password"]))
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


@bp.post("/auth/login")
def login():
    data = json_body()
    require_fields(data, "username", "password")
    ident = str(data["username"]).strip()
    user = User.query.filter(or_(User.username == ident, User.email == ident.lower())).first()
    if not user or not user.is_active or not user.check_password(str(data["password"])):
        raise ApiError("Invalid credentials", 401)
    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    return jsonify({"access_token": token, "user": user.to_dict()})


@bp.get("/auth/me")
@login_required
def me():
    return jsonify(current_user().to_dict())


@bp.get("/users")
@roles_required("admin")
def list_users():
    return jsonify([u.to_dict() for u in User.query.order_by(User.id).all()])


@bp.patch("/users/<int:user_id>")
@roles_required("admin")
def update_user(user_id):
    user = db.get_or_404(User, user_id)
    data = json_body()
    if "role" in data:
        if data["role"] not in ROLES:
            raise ApiError(f"role must be one of {sorted(ROLES)}")
        user.role = data["role"]
    if "is_active" in data:
        if user.id == current_user().id and not data["is_active"]:
            raise ApiError("You cannot disable your own account")
        user.is_active = bool(data["is_active"])
    db.session.commit()
    return jsonify(user.to_dict())
