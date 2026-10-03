from flask import Blueprint

configurations_bp = Blueprint('configurations', __name__, template_folder='../templates')

from app.configurations import routes
