from flask import Blueprint, render_template, request, abort, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import or_
from app.extensions import db
from app.models.user_model import User
from app.models.person_model import Person
from app.models.company_model import Company
from app.models.institutional_staff_model import InstitutionalStaff
from app.models.company_staff_model import CompanyStaff
from app.models.role_model import Role
from app.models.state_model import State
from app.models.institution_model import Institution
from app.models.place_model import Place
from app.models.parish_model import Parish
from app.models.municipality_model import Municipality

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
    filter_municipality = request.args.get('municipality', '')
    filter_parish = request.args.get('parish', '')

    filters = {
        'search': search_query,
        'role': filter_role,
        'status': filter_status,
        'state': filter_state,
        'municipality': filter_municipality,
        'parish': filter_parish
    }

    try:
        # 1. Cargamos los catálogos base
        db_roles = Role.query.all()
        db_states = State.query.all()
        db_municipalities = []
        db_parishes = []
        
        # Traducimos los roles usando versiones cortas
        for r in db_roles:
            if r.name == 'super_admin':
                r.translated_name = 'Super Admin'
            elif r.name == 'state_admin':
                r.translated_name = 'Admin Estadal'
            elif r.name in ['director', 'directora', 'applicant']:
                r.translated_name = 'Solicitante'
            else:
                r.translated_name = r.name.title()

        query = User.query
        query = query.outerjoin(Person)
        
        # --- TAREA: El Admin Estadal solo debe ver a los roles solicitantes ---
        if user_role == 'state_admin':
            applicant_roles = [r.id for r in db_roles if r.name in ['applicant', 'director', 'directora']]
            if applicant_roles:
                conditions = [User.roles_assoc.any(role_id=r_id) for r_id in applicant_roles]
                query = query.filter(or_(*conditions))

        # --- FILTRO GEOGRÁFICO DINÁMICO ---
        target_state_id = None
        
        if user_role == 'state_admin' and current_user.person:
            admin_inst = InstitutionalStaff.query.filter_by(person_id=current_user.person.id).first()
            if admin_inst and admin_inst.institution and admin_inst.institution.parish:
                target_state_id = admin_inst.institution.parish.municipality.state_id
            else:
                admin_comp = CompanyStaff.query.filter_by(person_id=current_user.person.id).first()
                if admin_comp and admin_comp.place and admin_comp.place.parish:
                    target_state_id = admin_comp.place.parish.municipality.state_id
                    
        elif user_role == 'super_admin' and filter_state and filter_state.isdigit():
            target_state_id = int(filter_state)

        if target_state_id:
            # Enviamos municipios del estado objetivo al HTML para el filtro de Admin Estadal
            db_municipalities = Municipality.query.filter_by(state_id=target_state_id).all()
            municipality_ids = [m.id for m in db_municipalities]
            
            # Enviamos las parroquias del estado objetivo al HTML
            if municipality_ids:
                db_parishes = Parish.query.filter(Parish.municipality_id.in_(municipality_ids)).all()
            
            # --- EVALUACIÓN DE FILTROS SELECCIONADOS ---
            if filter_parish and filter_parish.isdigit():
                parish_ids = [int(filter_parish)]
            elif filter_municipality and filter_municipality.isdigit():
                m_parishes = Parish.query.filter_by(municipality_id=int(filter_municipality)).all()
                parish_ids = [p.id for p in m_parishes]
            else:
                parish_ids = [p.id for p in db_parishes] if db_parishes else []
            
            if parish_ids:
                inst_staffs = InstitutionalStaff.query.join(Institution).filter(Institution.parish_id.in_(parish_ids)).all()
                comp_staffs = CompanyStaff.query.join(Place).filter(Place.parish_id.in_(parish_ids)).all()

                valid_person_ids = [staff.person_id for staff in inst_staffs] + [staff.person_id for staff in comp_staffs]
                query = query.filter(User.person_id.in_(valid_person_ids))
            else:
                query = query.filter(User.id == 0)
        elif user_role == 'state_admin' and not target_state_id:
             # Falla de seguridad: si el Admin Estadal no tiene estado asignado, bloqueamos los registros
             query = query.filter(User.id == 0)
        # --- FIN DEL FILTRO GEOGRÁFICO ---
            
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

        # Solo el super_admin puede filtrar por rol directamente desde la vista
        if user_role == 'super_admin' and filter_role and filter_role.isdigit():
            query = query.filter(User.roles_assoc.any(role_id=int(filter_role)))

        if filter_status:
            query = query.filter(User.status_id == int(filter_status))

        pagination = query.order_by(User.id.desc()).paginate(page=page, per_page=10, error_out=False)
        users_list = pagination.items

        # 2. Rescatamos el Estado geográfico correcto de cada usuario para la tabla
        for u in users_list:
            u.state_name = "Sin Asignar"
            if u.person:
                inst_staff = InstitutionalStaff.query.filter_by(person_id=u.person.id).first()
                if inst_staff and inst_staff.institution:
                    try:
                        u.state_name = inst_staff.institution.parish.municipality.state.name
                    except AttributeError:
                        pass
                else:
                    comp_staff = CompanyStaff.query.filter_by(person_id=u.person.id).first()
                    if comp_staff and comp_staff.place:
                        try:
                            u.state_name = comp_staff.place.parish.municipality.state.name
                        except AttributeError:
                            pass
        
    except Exception as e:
        print(f"Error en filtros: {e}")
        users_list = []
        pagination = None
        db_roles = []
        db_states = []
        db_municipalities = []
        db_parishes = []
    
    return render_template(
        'users/list.html',
        users=users_list,
        pagination=pagination,
        current_role=user_role,
        filters=filters,
        db_roles=db_roles,
        db_states=db_states,
        db_municipalities=db_municipalities,
        db_parishes=db_parishes
    )

@users_bp.route('/view/<int:user_id>', methods=['GET'])
@login_required
def view_user(user_id):
    user = User.query.get_or_404(user_id)
    person = user.person
    user_role = current_user.roles_assoc[0].role.name if current_user.roles_assoc else 'applicant'

    # --- FUNCIONES DE FORMATO ---
    def format_venezuelan_id(id_str):
        if not id_str: return 'N/A'
        id_clean = str(id_str).strip().upper().replace('-', '')
        if id_clean.startswith(('V', 'E', 'J', 'G', 'P')):
            return f"({id_clean[0]}-{id_clean[1:]})"
        return f"(V-{id_clean})"

    def format_venezuelan_phone(phone_str):
        if not phone_str or phone_str == 'N/A': return 'N/A'
        clean_phone = ''.join(filter(str.isdigit, str(phone_str)))
        if len(clean_phone) >= 10:
            return f"({clean_phone[:4]})-{clean_phone[4:]}"
        return phone_str
    # ----------------------------

    corp_data = None
    
    if person:
        # 1. Identificación y Contacto Personal
        person_id_val = getattr(person, 'identification_number', getattr(person, 'id_card', ''))
        user.formatted_id = format_venezuelan_id(person_id_val)
        
        user.formatted_phone = format_venezuelan_phone(getattr(person, 'mobile', ''))
        user.formatted_phone_sec = format_venezuelan_phone(getattr(person, 'phone', ''))

        # 2. Búsqueda de Institución / Empresa
        inst_staff = InstitutionalStaff.query.filter_by(person_id=person.id).first()
        
        if inst_staff:
            inst = inst_staff.institution
            pos = inst_staff.position
            
            city_name = 'N/A'
            if inst and getattr(inst, 'parish_id', None):
                try:
                    from app.models.location_model import Location
                    loc = Location.query.filter_by(parish_id=inst.parish_id).first()
                    if loc and loc.city:
                        city_name = loc.city.name
                except Exception:
                    pass
            
            corp_data = {
                'id_card': inst.institution_code if inst else 'N/A',
                'name': inst.institution_name if inst else 'N/A',
                'type': inst.institution_type.name if inst and getattr(inst, 'institution_type', None) else 'N/A',
                'sector': inst.institution_scope.name if inst and getattr(inst, 'institution_scope', None) else 'N/A',
                'dependency': inst.institution_dependency.name if inst and getattr(inst, 'institution_dependency', None) else 'N/A',
                'position': pos.name if pos else 'N/A',
                'phone_main': format_venezuelan_phone(getattr(inst, 'phone', 'N/A')),
                'phone_sec': 'N/A',
                'state': inst.parish.municipality.state.name if inst and getattr(inst, 'parish', None) and getattr(inst.parish, 'municipality', None) else 'N/A',
                'municipality': inst.parish.municipality.name if inst and getattr(inst, 'parish', None) else 'N/A',
                'parish': inst.parish.name if inst and getattr(inst, 'parish', None) else 'N/A',
                'city': city_name, 
                'address': inst.address if inst else 'N/A'
            }
        else:
            comp_staff = CompanyStaff.query.filter_by(person_id=person.id).first()
            
            if comp_staff:
                place = comp_staff.place
                comp = place.company if place else None
                pos = comp_staff.position
                
                city_name = 'N/A'
                if place and getattr(place, 'parish_id', None):
                    try:
                        from app.models.location_model import Location
                        loc = Location.query.filter_by(parish_id=place.parish_id).first()
                        if loc and loc.city:
                            city_name = loc.city.name
                    except Exception:
                        pass
                
                if comp:
                    corp_data = {
                        'id_card': comp.rif,
                        'name': comp.company_name,
                        'type': 'Empresa Privada', 
                        'sector': 'N/A',
                        'dependency': 'N/A',
                        'position': pos.name if pos else 'N/A',
                        'phone_main': format_venezuelan_phone(getattr(place, 'phone', 'N/A')),
                        'phone_sec': 'N/A',
                        'state': place.parish.municipality.state.name if place and getattr(place, 'parish', None) and getattr(place.parish, 'municipality', None) else 'N/A',
                        'municipality': place.parish.municipality.name if place and getattr(place, 'parish', None) else 'N/A',
                        'parish': place.parish.name if place and getattr(place, 'parish', None) else 'N/A',
                        'city': city_name,
                        'address': place.address if place else 'N/A'
                    }

    return render_template('users/view_user.html', user=user, corp_data=corp_data, current_role=user_role)

