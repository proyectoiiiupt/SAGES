"""
Rutas del Módulo de Formación
Define los endpoints para la gestión del catálogo de formación.
"""
from flask import render_template, flash, redirect, request, url_for
from flask_login import login_required
from app.trainings import trainings_bp
from app.trainings.services import get_all_trainings, get_filter_options

@trainings_bp.route('/catalog', methods=['GET'])
@login_required
def catalog():
    """
    Vista para el catálogo de formación con buscador rápido, filtros combinados y paginación.
    Accesible para todos los usuarios autenticados.

    Funcionalidades:
    - Búsqueda rápida por nombre, código o descripción
    - Filtros combinados por categoría y estatus
    - Paginación de 10 registros por página
    - Diseño tabular responsivo
    """
    try:
        # Obtener filtros de la URL
        filters = {
            'search_name': request.args.get('search_name'),
            'category': request.args.get('category'),
            'status': request.args.get('status')
        }

        # Convertir a enteros solo category, mantener status como texto y search_name como texto
        filters = {k: int(v) if v and k == 'category' else v for k, v in filters.items()}

        # Obtener parámetros de paginación
        page = request.args.get('page', 1, type=int)
        per_page = 10  # Fijado a 10 filas por página

        # Obtener datos paginados y opciones de filtros
        pagination_data = get_all_trainings(filters, page=page, per_page=per_page)
        filter_options = get_filter_options()

        pagination = pagination_data['pagination']

        return render_template('trainings/catalog.html',
                             trainings=pagination_data['trainings'],
                             pagination=pagination,
                             filter_options=filter_options,
                             current_filters=filters)
    except Exception as e:
        print(f"Error en catalog: {e}")
        flash("Error al cargar el catálogo de formación", 'danger')

        # Crear un objeto de paginación mínimo para evitar errores en el template
        class FakePagination:
            def __init__(self):
                self.total = 0
                self.pages = 0
                self.page = 1
                self.has_prev = False
                self.has_next = False
                self.prev_num = None
                self.next_num = None
                self.items = []

            def iter_pages(self, left_edge=2, left_current=2, right_current=3, right_edge=2):
                return []

        return render_template('trainings/catalog.html',
                             trainings=[],
                             pagination=FakePagination(),
                             filter_options={'categories': [], 'statuses': []},
                             current_filters={})