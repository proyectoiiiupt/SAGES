from flask import Blueprint, render_template, request, abort, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db
from app.models.user_model import User
from app.models.person_model import Person
from app.models.company_model import Company
from app.models.institutional_staff_model import InstitutionalStaff
from app.models.company_staff_model import CompanyStaff

# definimos el blueprint

users_bp = Blueprint('users', __name__)

@users_bp.route('/list', methods=['GET'])
@login_required
def list_users():
    user_role = current_user.roles_assoc[0].role.name if current_user.roles_assoc else 'applicant'
    
    if user_role not in ['super_admin', 'state_admin']:
        abort(403)

    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()
    filter_role = request.args.get('role', '')
    filter_status = request.args.get('status', '')
    filter_state = request.args.get('state', '')

    filters = {
        'search': search_query,
        'role': filter_role,
        'status': filter_status,
        'state': filter_state
    }

    try:
        query = User.query
        query = query.outerjoin(Person)
        
        if user_role == 'state_admin':
            if current_user.person:
                query = query.filter(User.person.has(state_id=current_user.person.state_id))
        elif user_role == 'super_admin' and filter_state:
            query = query.filter(Person.state_id == int(filter_state))
            
        if search_query:
            search_pattern = f"%{search_query}%"
            if search_query.isdigit():
                query = query.filter(
                    (Person.identification_number.ilike(search_pattern)) |
                    (User.user_name.ilike(search_pattern)) |
                    (User.id == int(search_query))
                )
            else:
                query = query.filter(
                    (User.user_name.ilike(search_pattern)) |
                    (Person.first_name.ilike(search_pattern)) |
                    (Person.last_name.ilike(search_pattern)) |
                    (Person.identification_number.ilike(search_pattern))
                )

        if filter_role and filter_role.isdigit():
            query = query.filter(User.roles_assoc.any(role_id=int(filter_role)))

        if filter_status:
            query = query.filter(User.status_id == int(filter_status))

        pagination = query.order_by(User.id.desc()).paginate(page=page, per_page=10, error_out=False)
        users_list = pagination.items
        
    except Exception as e:
        print(f"Error en filtros: {e}")
        users_list = []
        pagination = None
    
    return render_template(
        'users/list.html',
        users=users_list,
        pagination=pagination,
        current_role=user_role,
        filters=filters
    )

@users_bp.route('/view/<int:user_id>', methods=['GET'])
@login_required
def view_user(user_id):
    user = User.query.get_or_404(user_id)
    person = user.person
    user_role = current_user.roles_assoc[0].role.name if current_user.roles_assoc else 'applicant'

    corp_data = None
    
    if person:
        # 1. Buscamos primero si el usuario pertenece a una Institución
        inst_staff = InstitutionalStaff.query.filter_by(person_id=person.id).first()
        
        if inst_staff:
            inst = inst_staff.institution
            pos = inst_staff.position
            
            corp_data = {
                'id_card': inst.institution_code if inst else 'N/A',
                'name': inst.institution_name if inst else 'N/A',
                'type': inst.institution_type.name if inst and getattr(inst, 'institution_type', None) else 'N/A',
                'sector': inst.institution_scope.name if inst and getattr(inst, 'institution_scope', None) else 'N/A',
                'dependency': inst.institution_dependency.name if inst and getattr(inst, 'institution_dependency', None) else 'N/A',
                'position': pos.name if pos else 'N/A',
                'phone_main': inst.phone if inst else 'N/A',
                'phone_sec': 'N/A', # La tabla institutions no posee un segundo teléfono
                'state': inst.parish.municipality.state.name if inst and getattr(inst, 'parish', None) and getattr(inst.parish, 'municipality', None) else 'N/A',
                'municipality': inst.parish.municipality.name if inst and getattr(inst, 'parish', None) else 'N/A',
                'parish': inst.parish.name if inst and getattr(inst, 'parish', None) else 'N/A',
                'address': inst.address if inst else 'N/A'
            }
        else:
            # 2. Si no es de una Institución, buscamos si pertenece a una Empresa Privada
            comp_staff = CompanyStaff.query.filter_by(person_id=person.id).first()
            
            if comp_staff:
                place = comp_staff.place
                comp = place.company if place else None
                pos = comp_staff.position
                
                if comp:
                    corp_data = {
                        'id_card': comp.rif,
                        'name': comp.company_name,
                        'type': 'Empresa Privada', 
                        'sector': 'N/A',
                        'dependency': 'N/A',
                        'position': pos.name if pos else 'N/A',
                        'phone_main': place.phone if place else 'N/A',
                        'phone_sec': 'N/A',
                        'state': place.parish.municipality.state.name if place and getattr(place, 'parish', None) and getattr(place.parish, 'municipality', None) else 'N/A',
                        'municipality': place.parish.municipality.name if place and getattr(place, 'parish', None) else 'N/A',
                        'parish': place.parish.name if place and getattr(place, 'parish', None) else 'N/A',
                        'address': place.address if place else 'N/A'
                    }

    return render_template('users/view_user.html', user=user, corp_data=corp_data, current_role=user_role)

@users_bp.route('/toggle_status/<int:user_id>', methods=['POST'])
@login_required
def toggle_user_status(user_id):
    # Verificamos el rol para asegurarnos de que SOLO el super_admin pueda hacer esto
    user_role = current_user.roles_assoc[0].role.name if current_user.roles_assoc else 'applicant'
    
    if user_role != 'super_admin':
        abort(403) # Acceso denegado si alguien intenta forzar la ruta
        
    user = User.query.get_or_404(user_id)
    
    # Lógica para alternar el estado (1 = Activo, 2 = Inactivo)
    if user.status_id == 1:
        user.status_id = 2
    else:
        user.status_id = 1
        
    db.session.commit()
    
    # Recargamos la vista del perfil para ver el interruptor actualizado
    return redirect(url_for('users.view_user', user_id=user.id))