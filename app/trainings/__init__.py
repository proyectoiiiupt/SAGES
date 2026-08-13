from flask import Blueprint

trainings_bp = Blueprint('trainings', __name__)

from app.trainings import routes