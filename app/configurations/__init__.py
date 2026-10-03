from flask import Blueprint

configurations_bp = Blueprint('configurations', __name__)

from app.configurations import routes
