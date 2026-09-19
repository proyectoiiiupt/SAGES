"""
Módulo de Formación (Trainings)
Gestiona la visualización del catálogo de Módulos Rectores de la UREE
y los Temas Formativos asociados.

Funcionalidades del Bloque 1:
  - Hub de navegación (vista principal / landing) con tarjetas interactivas.
  - Endpoint asíncrono para conteos de temas por módulo según rol.
"""
from flask import Blueprint

# Blueprint del módulo de Formación
trainings_bp = Blueprint('trainings', __name__)

# Importar las rutas del módulo para registrarlas en el blueprint
from app.trainings import routes
