import datetime
from flask import Blueprint, render_template, request, abort, redirect, url_for, flash, jsonify, current_app, send_from_directory
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
from app.models.staff_evidence_model import StaffEvidence
from app.models.position_model import Position  
from app.models.status_model import Status
from app.users.forms import UserUpdateForm, AdminUserRegisterForm
from app.utils.activation_utils import generate_activation_token
from app.utils.email_utils import send_applicant_activation_email, send_administrative_activation_email
from app.users.services import get_corpoelec_places_by_state, get_administrative_positions, create_administrative_user
from app.binnacle.decorators import audit_activity
from app.binnacle.services import BinnacleService
from app.binnacle.types import AuditModule, AuditAction, AuditStatus


users_bp = Blueprint('users', __name__)

def format_identification(id_type, id_number):
    """
    Formatea cédulas venezolanas sin paréntesis: V-12.345.678 o E-1.234.567
    Soporta 7 u 8 dígitos formateando miles con puntos.
    """
    if not id_number:
        return 'N/A'
    
    clean_type = str(id_type).strip().upper() if id_type else 'V'
    if clean_type not in ['V', 'E', 'J', 'G', 'P']:
        clean_type = 'V'

    clean_num = ''.join(filter(str.isdigit, str(id_number)))
    if not clean_num:
        return 'N/A'
        
    try:
        formatted_num = f"{int(clean_num):,}".replace(',', '.')
        return f"{clean_type}-{formatted_num}"
    except ValueError:
        return f"{clean_type}-{clean_num}"


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
        db_roles = Role.query.all()
        db_states = State.query.all()
        db_municipalities = []
        db_parishes = []
        
        for r in db_roles:
            if r.name == 'super_admin':
                r.translated_name = 'Super Admin'
            elif r.name == 'state_admin':
                r.translated_name = 'Admin Estadal'
            elif r.name in ['director', 'directora', 'applicant']:
                r.translated_name = 'Solicitante'
            else:
                r.translated_name = r.name.title()

        query = User.query.outerjoin(Person)
        
        # El Admin Estadal solo debe ver a los roles solicitantes
        if user_role == 'state_admin':
            applicant_roles = [r.id for r in db_roles if r.name in ['applicant', 'director', 'directora']]
            if applicant_roles:
                conditions = [User.roles_assoc.any(role_id=r_id) for r_id in applicant_roles]
                query = query.filter(or_(*conditions))

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
            db_municipalities = Municipality.query.filter_by(state_id=target_state_id).all()
            
            # FILTRO DINÁMICO DE PARROQUIA: Solo cargar parroquias si hay municipio seleccionado
            if filter_municipality and filter_municipality.isdigit():
                db_parishes = Parish.query.filter_by(municipality_id=int(filter_municipality)).all()
            else:
                db_parishes = []
            
            # Evaluación de filtros seleccionados
            if filter_parish and filter_parish.isdigit():
                parish_ids = [int(filter_parish)]
            elif filter_municipality and filter_municipality.isdigit():
                m_parishes = Parish.query.filter_by(municipality_id=int(filter_municipality)).all()
                parish_ids = [p.id for p in m_parishes]
            else:
                all_m_ids = [m.id for m in db_municipalities]
                parish_ids = [p.id for p in Parish.query.filter(Parish.municipality_id.in_(all_m_ids)).all()] if all_m_ids else []
            
            if parish_ids:
                inst_staffs = InstitutionalStaff.query.join(Institution).filter(Institution.parish_id.in_(parish_ids)).all()
                comp_staffs = CompanyStaff.query.join(Place).filter(Place.parish_id.in_(parish_ids)).all()

                valid_person_ids = [staff.person_id for staff in inst_staffs] + [staff.person_id for staff in comp_staffs]
                query = query.filter(User.person_id.in_(valid_person_ids))
            else:
                query = query.filter(User.id == 0)
        elif user_role == 'state_admin' and not target_state_id:
             query = query.filter(User.id == 0)
            
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

        if user_role == 'super_admin' and filter_role and filter_role.isdigit():
            query = query.filter(User.roles_assoc.any(role_id=int(filter_role)))

        if filter_status:
            query = query.filter(User.status_id == int(filter_status))

        pagination = query.order_by(User.id.desc()).paginate(page=page, per_page=10, error_out=False)
        users_list = pagination.items

        # Rescatamos datos de institución, ubicación y cédula formateada para cada usuario
        for u in users_list:
            u.state_name = "Sin Asignar"
            u.institution_name = "N/A"
            u.municipality_name = "N/A"
            u.parish_name = "N/A"
            u.formatted_id = "N/A"

            if u.person:
                id_type = getattr(u.person, 'identification_type', 'V')
                id_num = getattr(u.person, 'identification_number', getattr(u.person, 'id_card', ''))
                u.formatted_id = format_identification(id_type, id_num)

                inst_staff = InstitutionalStaff.query.filter_by(person_id=u.person.id).first()
                if inst_staff and inst_staff.institution:
                    u.institution_name = inst_staff.institution.institution_name
                    if inst_staff.institution.parish:
                        u.parish_name = inst_staff.institution.parish.name
                        if inst_staff.institution.parish.municipality:
                            u.municipality_name = inst_staff.institution.parish.municipality.name
                            u.state_name = inst_staff.institution.parish.municipality.state.name
                else:
                    comp_staff = CompanyStaff.query.filter_by(person_id=u.person.id).first()
                    if comp_staff and comp_staff.place:
                        if comp_staff.place.company:
                            u.institution_name = comp_staff.place.company.company_name
                        if comp_staff.place.parish:
                            u.parish_name = comp_staff.place.parish.name
                            if comp_staff.place.parish.municipality:
                                u.municipality_name = comp_staff.place.parish.municipality.name
                                u.state_name = comp_staff.place.parish.municipality.state.name
        
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
@audit_activity(module=AuditModule.USERS.value, action_type=AuditAction.CONSULTA_DETALLE.value, description="Consulta del perfil detallado de un usuario")
def view_user(user_id):
    user = User.query.get_or_404(user_id)
    person = user.person
    
    current_user_role = current_user.roles_assoc[0].role.name if current_user.roles_assoc else 'applicant'
    viewed_role = user.roles_assoc[0].role.name if user.roles_assoc else 'applicant'

    def format_venezuelan_phone(phone_str):
        if not phone_str or phone_str == 'N/A': return 'N/A'
        clean_phone = ''.join(filter(str.isdigit, str(phone_str)))
        if len(clean_phone) >= 10:
            return f"({clean_phone[:4]})-{clean_phone[4:]}"
        return phone_str

    corp_data = None
    
    if person:
        id_type = getattr(person, 'identification_type', 'V')
        person_id_val = getattr(person, 'identification_number', getattr(person, 'id_card', ''))
        user.formatted_id = format_identification(id_type, person_id_val)
        
        user.formatted_phone = format_venezuelan_phone(getattr(person, 'mobile', ''))
        user.formatted_phone_sec = format_venezuelan_phone(getattr(person, 'phone', ''))

        first_n = getattr(person, 'first_name', '') or ''
        second_n = getattr(person, 'second_name', '') or ''
        last_n = getattr(person, 'last_name', '') or ''
        middle_n = getattr(person, 'middle_name', '') or ''
        
        user.full_first_name = f"{first_n} {second_n}".strip() if first_n else 'N/A'
        user.full_last_name = f"{last_n} {middle_n}".strip() if last_n else 'N/A'

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
            
            plantel_code = getattr(inst, 'plantel_code', None)
            
            corp_data = {
                'id_card': plantel_code if plantel_code else 'N/A',
                'name': inst.institution_name if inst else 'N/A',
                'type': inst.institution_type.name if inst and getattr(inst, 'institution_type', None) else 'N/A',
                'sector': inst.institution_scope.name if inst and getattr(inst, 'institution_scope', None) else 'N/A',
                'dependency': inst.institution_dependency.name if inst and getattr(inst, 'institution_dependency', None) else 'N/A',
                'position': pos.name if pos else 'N/A',
                'phone_main': format_venezuelan_phone(getattr(inst, 'phone', 'N/A')),
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
                    type_rif = getattr(comp, 'identification_type', '') or ''
                    num_rif = getattr(comp, 'rif', '') or ''
                    formatted_rif = f"{type_rif}-{num_rif}".strip('-') if (type_rif or num_rif) else 'N/A'

                    corp_data = {
                        'id_card': formatted_rif,
                        'name': comp.company_name,
                        'type': 'Empresa Privada', 
                        'sector': 'N/A',
                        'dependency': 'N/A',
                        'position': pos.name if pos else 'N/A',
                        'phone_main': format_venezuelan_phone(getattr(place, 'phone', 'N/A')),
                        'state': place.parish.municipality.state.name if place and getattr(place, 'parish', None) and getattr(place.parish, 'municipality', None) else 'N/A',
                        'municipality': place.parish.municipality.name if place and getattr(place, 'parish', None) else 'N/A',
                        'parish': place.parish.name if place and getattr(place, 'parish', None) else 'N/A',
                        'city': city_name,
                        'address': place.address if place else 'N/A',
                        'sede': place.name if place else 'N/A'
                    }

    return render_template('users/view_user.html', user=user, corp_data=corp_data, current_role=current_user_role, viewed_role=viewed_role)

       
@users_bp.route('/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    """
    Ruta con validaciones JS combinadas con reglas de seguridad base.
    """
    user_role = current_user.roles_assoc[0].role.name if current_user.roles_assoc else 'applicant'
    
    # Solo el administrador puede actualizar datos base
    if user_role != 'super_admin':
        abort(403)

    user = User.query.get_or_404(user_id)
    person = user.person
    
    # Determinar si el usuario pertenece a una institución o empresa para el cargo
    inst_staff = InstitutionalStaff.query.filter_by(person_id=person.id).first()
    comp_staff = CompanyStaff.query.filter_by(person_id=person.id).first()
    staff_record = inst_staff or comp_staff
    
    form = UserUpdateForm() 
    
    # Poblamos las opciones del dropdown directamente desde la BD
    form.position.choices = [(p.id, p.name) for p in Position.query.order_by(Position.name).all()]

    if form.validate_on_submit():
        try:
            # Quitamos los puntos de la cédula antes de guardar en base de datos
            raw_cedula = form.identification_number.data.replace('.', '').strip()
            
            changed_fields = {}
            if person.identification_number != raw_cedula:
                changed_fields["Cédula"] = raw_cedula
            person.identification_number = raw_cedula
            
            new_first_name = form.first_name.data.strip().title()
            if person.first_name != new_first_name:
                changed_fields["Primer Nombre"] = new_first_name
            person.first_name = new_first_name
            
            new_second_name = form.second_name.data.strip().title() if form.second_name.data else None
            if person.second_name != new_second_name:
                changed_fields["Segundo Nombre"] = new_second_name if new_second_name else "S/D"
            person.second_name = new_second_name
            
            new_last_name = form.last_name.data.strip().title()
            if person.last_name != new_last_name:
                changed_fields["Primer Apellido"] = new_last_name
            person.last_name = new_last_name
            
            new_middle_name = form.middle_name.data.strip().title() if form.middle_name.data else None
            if person.middle_name != new_middle_name:
                changed_fields["Segundo Apellido"] = new_middle_name if new_middle_name else "S/D"
            person.middle_name = new_middle_name
            
            # Guardamos el nuevo cargo
            if staff_record and staff_record.position_id != form.position.data:
                pos_name = dict(form.position.choices).get(form.position.data, "Actualizado")
                changed_fields["Cargo"] = pos_name
                staff_record.position_id = form.position.data
                    
            db.session.commit()
            
            try:
                from app.notifications.services import NotificationService
                from app.notifications.enums import NotificationEvent
                
                # Agregar Modificado Por
                if current_user and hasattr(current_user, 'person') and current_user.person:
                    changed_fields["Modificado Por"] = f"{current_user.person.first_name} {current_user.person.last_name}".strip()
                else:
                    changed_fields["Modificado Por"] = "Administración Central"
                    
                # Solo notificar si realmente hubo un cambio
                if len(changed_fields) > 1:
                    NotificationService.notify_user(
                        user_id=user.id,
                        event=NotificationEvent.USER_PROFILE_UPDATED,
                        context={"_display": changed_fields},
                        redirect_url="/users/profile",
                        action_text="Revisar Perfil"
                    )
            except Exception as e:
                print(f"Error enviando notificacion de edicion de perfil: {e}")
            
            flash('Datos del usuario actualizados exitosamente.', 'success')
            return redirect(url_for('users.view_user', user_id=user.id))
            
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR EDIT USER]: {e}")
            flash('Ocurrió un error al intentar guardar en la base de datos.', 'error')
        
    elif request.method == 'POST':
    
       
        if person:
            person.identification_number = request.form.get('identification_number', person.identification_number)
            person.first_name = request.form.get('first_name', person.first_name)
            person.second_name = request.form.get('second_name', person.second_name)
            person.last_name = request.form.get('last_name', person.last_name)
            person.middle_name = request.form.get('middle_name', person.middle_name)

        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{error}", 'error')
    else:
        # Pre-seleccionar el cargo actual al cargar la vista GET
        if staff_record and staff_record.position_id:
            form.position.data = staff_record.position_id

    return render_template('users/edit_user.html', user=user, current_role=user_role, form=form)

@users_bp.route('/toggle_status/<int:user_id>', methods=['POST'])
@login_required
def toggle_status(user_id):
    """
    US-16: Activa o desactiva un usuario.
    """
    user_role = current_user.roles_assoc[0].role.name if current_user.roles_assoc else 'applicant'
    if user_role != 'super_admin':
        abort(403)

    user = User.query.get_or_404(user_id)
    
    # 1 = Activo, 2 = Inactivo
    old_status = user.status_id
    new_status = 2 if old_status == 1 else 1 
    
    user.status_id = new_status
    
    try:
        db.session.commit()
        
        estado_str = "activado" if new_status == 1 else "desactivado"
        
        BinnacleService.create_log_entry(
            module=AuditModule.USERS.value,
            action_type=AuditAction.CAMBIO_ESTATUS_USUARIO.value,
            description=f'El perfil del usuario ha sido {estado_str} exitosamente.',
            target_table='sages.users',
            record_id=user.id,
            status=AuditStatus.MODIFICADO.value
        )
        
        flash(f'El perfil del usuario ha sido {estado_str} exitosamente.', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"\n[ERROR TOGGLE STATUS]: {e}\n")
        flash('Ocurrió un error al intentar cambiar el estatus.', 'error')
        
    return redirect(url_for('users.view_user', user_id=user.id))

@users_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """
    Sección de Perfil de Usuario:
    - Consulta de datos fijos del usuario autenticado (personales, institucionales/corporativos).
    - Edición de datos de contacto (correo electrónico, teléfono principal y secundario).
    - Actualización de contraseña validando la clave actual y políticas de seguridad del sistema.
    """
    from app.users.forms import ChangePasswordForm, ProfileContactForm
    from app.users.services import get_user_profile_data, change_profile_password, update_user_contact

    password_form = ChangePasswordForm()
    contact_form = ProfileContactForm()
    active_tab = request.args.get('tab', 'personal')

    if request.method == 'POST':
        form_type = request.form.get('form_type', '')

        if form_type == 'contact':
            if contact_form.validate_on_submit():
                success, message = update_user_contact(
                    current_user,
                    contact_form.email.data,
                    contact_form.mobile.data,
                    contact_form.phone.data
                )
                if success:
                    flash(message, 'success')
                    return redirect(url_for('users.profile', tab='personal'))
                else:
                    flash(message, 'danger')
                    active_tab = 'personal'
            else:
                active_tab = 'personal'
                for field, errors in contact_form.errors.items():
                    for error in errors:
                        flash(error, 'danger')

        elif form_type == 'password' or not form_type:
            if password_form.validate_on_submit():
                current_pw = password_form.current_password.data
                new_pw = password_form.new_password.data
                confirm_pw = password_form.confirm_password.data

                success, message = change_profile_password(current_user, current_pw, new_pw, confirm_pw)

                if success:
                    flash(message, 'success')
                    return redirect(url_for('users.profile', tab='security'))
                else:
                    flash(message, 'danger')
                    active_tab = 'security'
            else:
                active_tab = 'security'
                for field, errors in password_form.errors.items():
                    for error in errors:
                        flash(error, 'danger')

    profile_data = get_user_profile_data(current_user)

    # Pre-llenar formulario de contacto en peticiones GET
    if request.method == 'GET':
        contact_form.email.data = profile_data.get('raw_email', '')
        contact_form.mobile.data = profile_data.get('raw_mobile', '')
        contact_form.phone.data = profile_data.get('raw_phone', '')

    return render_template(
        'users/profile.html',
        profile=profile_data,
        form=password_form,
        contact_form=contact_form,
        active_tab=active_tab
    )


# ==========================================
# BANDEJA DE SOLICITUDES (US-10)
# ==========================================

@users_bp.route('/requests', methods=['GET'])
@login_required
def list_requests():
    user_role = current_user.roles_assoc[0].role.name if current_user.roles_assoc else 'applicant'
    if user_role != 'state_admin':
        abort(403)

    target_state_id = None
    if current_user.person:
        admin_inst = InstitutionalStaff.query.filter_by(person_id=current_user.person.id).first()
        if admin_inst and admin_inst.institution and admin_inst.institution.parish:
            target_state_id = admin_inst.institution.parish.municipality.state_id
            
    # Filtro simplificado basado estrictamente en las instrucciones del líder técnico
    status_pending = Status.query.filter_by(status_code='STAT-004').first()
    pending_requests = InstitutionalStaff.query.filter_by(status_id=status_pending.id).all() if status_pending else []

    return render_template(
        'users/requests_list.html', 
        requests=pending_requests,
        current_role=user_role
    )

@users_bp.route('/descargar_evidencia/<path:filename>')
def serve_evidence(filename):
    directorio_base = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    
    # Agregamos estos prints para ver la ruta exacta en la terminal
    print(f"\n--- DEBUG EVIDENCIA ---")
    print(f"Directorio Base: {directorio_base}")
    print(f"Nombre del archivo (BD): {filename}")
    print(f"-----------------------\n")
    
    try:
        return send_from_directory(directorio_base, filename)
    except FileNotFoundError:
        print("ERROR: No se encontró el archivo en la ruta combinada.")
        abort(404)

import os
from app.models.staff_evidence_model import StaffEvidence

@users_bp.route('/requests/<int:staff_id>/evidence', methods=['GET'])
@login_required
def get_evidence(staff_id):
    # Buscamos la evidencia del usuario usando el modelo correcto
    evidence = StaffEvidence.query.filter_by(institutional_staff_id=staff_id).first()

    if not evidence or not evidence.file_path:
        return jsonify({"status": "error", "message": "No se encontró un archivo adjunto."}), 404

    # Normalizamos separadores de carpetas Windows / Linux
    raw_path = evidence.file_path.replace('\\', '/')

    # Conservamos la subcarpeta dentro de uploads/ para que send_from_directory no se pierda
    if 'uploads/' in raw_path:
        clean_path = raw_path.split('uploads/')[-1]
    elif 'staff_evidences/' in raw_path:
        clean_path = 'staff_evidences/' + raw_path.split('staff_evidences/')[-1]
    else:
        clean_path = os.path.basename(raw_path)

    file_url = url_for('users.serve_evidence', filename=clean_path)

    BinnacleService.create_log_entry(
        module=AuditModule.USERS.value,
        action_type=AuditAction.CONSULTA_EVIDENCIA.value,
        description=f'Consulta de evidencia para solicitante staff_id: {staff_id}',
        target_table='sages.staff_evidences',
        record_id=evidence.id,
        status=AuditStatus.COMPLETADO.value
    )

    return jsonify({
        "status": "success", 
        "file_url": file_url,
        "file_type": clean_path.split('.')[-1].lower() 
    })

@users_bp.route('/requests/<int:staff_id>/approve', methods=['POST'])
@login_required
def approve_request(staff_id):
    user_role = current_user.roles_assoc[0].role.name if current_user.roles_assoc else 'applicant'
    if user_role not in ['state_admin', 'super_admin']:
        return jsonify({'status': 'error', 'message': 'No tiene permisos para realizar esta acción.'}), 403

    staff = InstitutionalStaff.query.get_or_404(staff_id)
    person = staff.person

    if not person:
        return jsonify({'status': 'error', 'message': 'El registro no posee información de persona asociada.'}), 400

    # Comprobar que no posea ya una cuenta de usuario activa
    if person.user:
        return jsonify({'status': 'error', 'message': 'Esta persona ya posee un usuario registrado en el sistema.'}), 400

    try:  # CORREGIDO: ttry -> try
        # Generación del token seguro con vigencia de 48h
        payload = {
            'person_id': person.id,
            'staff_id': staff.id,
            'flow': 'applicant',
            'email': person.email
        }
        token = generate_activation_token(payload)

        # 1. Actualizar el estatus del InstitutionalStaff a STAT-006 (En Proceso)
        # DESCOMENTADO para cumplir con la Sección 3.2 del documento de especificaciones
        status_in_progress = Status.query.filter_by(status_code='STAT-006').first()
        if status_in_progress:
            staff.status_id = status_in_progress.id 
        db.session.commit()

        try:
            from app.notifications.services import NotificationService
            from app.notifications.enums import NotificationEvent
            user_name = f"{person.first_name} {person.last_name}".strip()
            inst_name = staff.institution.institution_name if hasattr(staff, 'institution') and staff.institution else "Plantel Asignado"
            state_name = "su jurisdicción"
            if hasattr(staff, 'institution') and staff.institution and staff.institution.parish and hasattr(staff.institution.parish, 'municipality') and staff.institution.parish.municipality and hasattr(staff.institution.parish.municipality, 'state'):
                state_name = staff.institution.parish.municipality.state.name
            
            admin_name = f"{current_user.person.first_name} {current_user.person.last_name}".strip() if current_user and hasattr(current_user, 'person') and current_user.person else "Administrador"
            
            context = {
                "user_name": user_name,
                "institution_name": inst_name,
                "state_name": state_name,
                "admin_name": admin_name,
                "_display": [
                    ("Estado", state_name),
                    ("Código de Plantel", staff.institution.plantel_code if hasattr(staff, 'institution') and staff.institution else "S/D"),
                    ("Institución", inst_name),
                    ("Representante", user_name),
                    ("Cargo", staff.position.name if hasattr(staff, 'position') and staff.position else "Directivo/Encargado")
                ]
            }
            NotificationService.notify_role(
                role_name='super_admin',
                event=NotificationEvent.REGISTRATION_APPROVED,
                context=context
            )
        except Exception as e:
            print(f"Error enviando notificacion de aprobacion: {e}")

        BinnacleService.create_log_entry(
            module=AuditModule.USERS.value,
            action_type=AuditAction.APROBACION_SOLICITUD_REGISTRO.value,
            description=f'Solicitud aprobada exitosamente para {person.first_name} {person.last_name}',
            target_table='sages.institutional_staff',
            record_id=staff.id,
            status=AuditStatus.COMPLETADO.value
        )

        # 2. Llamada a la función de correo en hilo independiente DESPUÉS del commit
        send_applicant_activation_email(person.email, token)

        return jsonify({
            'status': 'success',
            'message': f'Solicitud aprobada exitosamente. Se ha generado el enlace de activación para {person.first_name} {person.last_name}.'
        })

    except Exception as e:
        db.session.rollback()
        print(f"[ERROR APPROVE REQUEST]: {e}")
        return jsonify({'status': 'error', 'message': 'Ocurrió un error interno al procesar la aprobación.'}), 500


# ==========================================
# REGISTRO ADMINISTRATIVO INTERNO (US-13)
# ==========================================

@users_bp.route('/api/validate-identification', methods=['GET'])
@login_required
def validate_identification():
    id_number = request.args.get('id', '').strip()
    if not id_number:
        return jsonify({'valid': False, 'message': 'Cédula requerida'})
    
    person = Person.query.filter_by(identification_number=id_number).first()
    if person:
        return jsonify({'valid': False, 'message': 'Esta cédula ya está registrada'})
    
    return jsonify({'valid': True})

@users_bp.route('/api/validate-email', methods=['GET'])
@login_required
def validate_email():
    email = request.args.get('email', '').strip().lower()
    if not email:
        return jsonify({'valid': False, 'message': 'Correo requerido'})
        
    person = Person.query.filter(db.func.lower(Person.email) == email).first()
    if person:
        return jsonify({'valid': False, 'message': 'Este correo ya está registrado'})
        
    return jsonify({'valid': True})

@users_bp.route('/api/places-by-state/<int:state_id>', methods=['GET'])
@login_required
def api_places_by_state(state_id):
    places = get_corpoelec_places_by_state(state_id)
    return jsonify(places)

@users_bp.route('/register', methods=['GET', 'POST'])
@login_required
def register_admin():
    user_role = current_user.roles_assoc[0].role.name if current_user.roles_assoc else 'applicant'
    if user_role not in ['super_admin']:
        abort(403)
        
    form = AdminUserRegisterForm()
    
    # Cargar roles permitidos
    _role_names = {'super_admin': 'Super Administrador', 'state_admin': 'Administrador Estadal'}
    form.role_id.choices = [('', 'Seleccione un rol...')] + [
        (str(r.id), _role_names.get(r.name, r.name.title())) 
        for r in Role.query.filter(Role.role_code.in_(['ROL-001', 'ROL-002'])).all()
    ]
    
    # Cargar estados
    form.state_id.choices = [('', 'Seleccione un estado...')] + [(str(s.id), s.name) for s in State.query.order_by(State.name).all()]
    
    # Cargar cargos administrativos
    form.position_id.choices = [('', 'Seleccione un cargo...')] + [(str(p['id']), p['name']) for p in get_administrative_positions()]
    
    # Las sedes se cargan dinámicamente, pero para POST validación agregamos la seleccionada
    if request.method == 'POST' and form.state_id.data:
        try:
            state_id = int(form.state_id.data)
            places = get_corpoelec_places_by_state(state_id)
            form.place_id.choices = [('', 'Seleccione una sede...')] + [(str(p['id']), p['name']) for p in places]
        except ValueError:
            form.place_id.choices = [('', 'Seleccione una sede...')]
    else:
        form.place_id.choices = [('', 'Seleccione una sede...')]

    if form.validate_on_submit():
        data = {
            'identification_type': form.identification_type.data,
            'identification_number': form.identification_number.data,
            'first_name': form.first_name.data.title(),
            'second_name': form.second_name.data.title() if form.second_name.data else None,
            'last_name': form.last_name.data.title(),
            'middle_name': form.middle_name.data.title() if form.middle_name.data else None,
            'email': form.email.data.lower(),
            'mobile': form.mobile.data,
            'phone': form.phone.data if form.phone.data else None,
            'role_id': int(form.role_id.data),
            'state_id': int(form.state_id.data),
            'place_id': int(form.place_id.data),
            'position_id': int(form.position_id.data),
            'is_active': False
        }
        
        success, message, result_data = create_administrative_user(data, current_user)
        
        if success:
            # Generar token y enviar correo
            payload = {
                'person_id': result_data['person_id'],
                'staff_id': result_data['staff_id'],
                'flow': 'administrative',
                'role_id': result_data['role_id'],
                'email': result_data['email']
            }
            token = generate_activation_token(payload)
            send_administrative_activation_email(
                to_email=result_data['email'],
                token=token,
                role_display=result_data['role_display'],
                place_name=result_data['place_name'],
                full_name=result_data['full_name']
            )
            
            BinnacleService.create_log_entry(
                module=AuditModule.USERS.value,
                action_type=AuditAction.REGISTRO_ADMIN_INTERNO.value,
                description=f'Alta corporativa de {result_data["role_display"]}: {result_data["full_name"]} asignado a sede {result_data["place_name"]}',
                target_table='sages.users',
                record_id=result_data['user_id'],
                status=AuditStatus.COMPLETADO.value
            )
            
            flash(message, 'success')
            return redirect(url_for('users.list_users'))
        else:
            flash(message, 'danger')
            


    return render_template('users/register_admin.html', form=form, current_role=user_role)
