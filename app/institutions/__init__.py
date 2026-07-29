"""
Módulo de Instituciones
Este módulo gestiona la visualización y administración básica de instituciones educativas.
Funcionalidades: Listado, visualización de detalles y cambio de estatus (Activo/Inactivo).
"""
from flask import Blueprint

# Blueprint del módulo de instituciones
# Permite organizar las rutas relacionadas con instituciones en un grupo con prefijo '/institutions'
institutions_bp = Blueprint('institutions', __name__)

# Importar las rutas del módulo para registrarlas en el blueprint
from app.institutions import routes