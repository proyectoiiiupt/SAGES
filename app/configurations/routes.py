"""
Rutas del Módulo de Configuraciones Globales (SAGES)
Tarea: US-53-settings-ui-prototype
Controlador mínimo en Flask para el acceso al panel administrativo de configuraciones.
"""

from flask import render_template
from flask_login import login_required
from app.configurations import configurations_bp
from app.decorators import role_required


@configurations_bp.route('/', methods=['GET'])
@login_required
@role_required('super_admin')
def index():
    """
    Ruta base del módulo de configuraciones.
    Renderiza el prototipo de interfaz con navegación de subvistas del lado del cliente.
    """
    return render_template('configurations/index.html')
