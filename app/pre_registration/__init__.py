from flask import Blueprint

pre_registration_bp = Blueprint('pre_registration', __name__)

from app.pre_registration import routes
