from flask import Blueprint

requests_bp = Blueprint('requests', __name__)

from app.requests import routes
