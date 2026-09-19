import csv
from io import StringIO
from flask import Blueprint, jsonify, render_template, request, Response
from app.models.binnacle_model import Binnacle 
from app.models.user_model import User

binnacle_bp = Blueprint('binnacle', __name__, url_prefix='/binnacle')

# --- RUTA PARA MOSTRAR LA PANTALLA ---
@binnacle_bp.route('/', methods=['GET'])
def index():
    registros = Binnacle.query.order_by(Binnacle.created_at.desc()).limit(20).all()
    
    logs_formateados = []
    for r in registros:
        logs_formateados.append({
            "id": r.id,
            "date": r.created_at.strftime("%Y-%m-%d %I:%M %p") if r.created_at else "",
            "user": r.user.full_name if r.user else "No registrado",
            "module": r.module,
            "action": r.action_type,
            "desc": r.description[:45] + "..." if r.description else "",
            "status": "Fallido" if "FALLIDO" in (r.action_type or "").upper() else "Completado"
        })
        
    return render_template('audit_log.html', logs=logs_formateados)

# --- RUTA DEL MODAL FORENSE ---
@binnacle_bp.route('/api/logs/<int:log_id>', methods=['GET'])
def get_log_details(log_id):
    log = Binnacle.query.get(log_id)
    
    if not log:
        return jsonify({"success": False, "message": "Registro no encontrado."}), 404

    fecha_form = log.created_at.strftime("%d/%m/%Y, %I:%M:%S %p UTC") if log.created_at else "Desconocida"

    if log.user:
        user_data = {
            "full_name": getattr(log.user, 'full_name', 'Nombre no disponible'),
            "role": getattr(log.user, 'role', 'Rol no disponible'),
            "identifier": getattr(log.user, 'identifier', 'ID no disponible')
        }
    else:
        user_data = {"full_name": "Usuario No Registrado", "role": "N/A", "identifier": "N/A"}

    diff_list = []
    old_data = log.old_values or {}
    new_data = log.new_values or {}
    
    for key in set(old_data.keys()).union(set(new_data.keys())):
        old_val = old_data.get(key)
        new_val = new_data.get(key)
        if old_val != new_val:
            diff_list.append({
                "field_label": key.replace('_', ' ').capitalize(), 
                "old_value": old_val, 
                "new_value": new_val
            })

    status_asignado = "Fallido" if "FALLIDO" in log.action_type.upper() else "Modificado" if diff_list else "Completado"

    response_data = {
        "id": log.id,
        "created_at_formatted": fecha_form,
        "user": user_data,
        "network": {"ip_address": log.ip_address or "N/A", "user_agent": log.user_agent or "N/A"},
        "operation": {
            "module": log.module, 
            "action_type": log.action_type, 
            "status": status_asignado,  
            "description": log.description, 
            "target_table": log.target_table or "N/A", 
            "record_id": log.record_id or "N/A"
        },
        "diff": diff_list
    }
    return jsonify({"success": True, "data": response_data}), 200

# --- RUTA PARA FILTROS Y PAGINACIÓN ---
@binnacle_bp.route('/api/logs', methods=['GET'])
def get_logs_filtered():
    page = request.args.get('page', 1, type=int)
    fecha_desde = request.args.get('fecha_desde')
    fecha_hasta = request.args.get('fecha_hasta')
    modulo = request.args.get('modulo')
    accion = request.args.get('accion')
    usuario = request.args.get('usuario')  
    estatus = request.args.get('estatus')  
    
    query = Binnacle.query

    if fecha_desde:
        query = query.filter(Binnacle.created_at >= f"{fecha_desde} 00:00:00")
    if fecha_hasta:
        query = query.filter(Binnacle.created_at <= f"{fecha_hasta} 23:59:59")
    if modulo:
        query = query.filter(Binnacle.module == modulo)
    if accion:
        query = query.filter(Binnacle.action_type == accion)
        
    if usuario:
        query = query.join(Binnacle.user).filter(User.full_name.ilike(f"%{usuario}%"))
        
    if estatus:
        if estatus == "Fallido":
            query = query.filter(Binnacle.action_type.ilike("%FALLIDO%"))
        elif estatus == "Completado":
            query = query.filter(~Binnacle.action_type.ilike("%FALLIDO%"))

    query = query.order_by(Binnacle.created_at.desc())
    pagination = query.paginate(page=page, per_page=15, error_out=False)
    
    logs_formateados = []
    for r in pagination.items:
        logs_formateados.append({
            "id": r.id,
            "date": r.created_at.strftime("%Y-%m-%d %I:%M %p") if r.created_at else "",
            "user": getattr(r.user, 'full_name', 'No registrado') if r.user else "No registrado",
            "module": r.module,
            "action": r.action_type,
            "desc": (r.description[:45] + "...") if r.description and len(r.description) > 45 else (r.description or ""),
            "status": "Fallido" if "FALLIDO" in (r.action_type or "").upper() else "Completado"
        })
        
    return jsonify({
        "success": True,
        "data": logs_formateados,
        "pagination": {
            "total": pagination.total,
            "pages": pagination.pages,
            "current_page": pagination.page
        }
    }), 200

# --- RUTA PARA EXPORTAR A CSV (CORREGIDA PARA EL FRONTEND) ---
@binnacle_bp.route('/api/logs/export', methods=['GET'])
def export_logs():
    fecha_desde = request.args.get('fecha_desde')
    fecha_hasta = request.args.get('fecha_hasta')
    modulo = request.args.get('modulo')
    accion = request.args.get('accion')
    usuario = request.args.get('usuario')
    estatus = request.args.get('estatus')
    
    query = Binnacle.query

    if fecha_desde: query = query.filter(Binnacle.created_at >= f"{fecha_desde} 00:00:00")
    if fecha_hasta: query = query.filter(Binnacle.created_at <= f"{fecha_hasta} 23:59:59")
    if modulo: query = query.filter(Binnacle.module == modulo)
    if accion: query = query.filter(Binnacle.action_type == accion)
    
    if usuario:
        query = query.join(Binnacle.user).filter(User.full_name.ilike(f"%{usuario}%"))
        
    if estatus:
        if estatus == "Fallido": query = query.filter(Binnacle.action_type.ilike("%FALLIDO%"))
        elif estatus == "Completado": query = query.filter(~Binnacle.action_type.ilike("%FALLIDO%"))
    
    registros = query.order_by(Binnacle.created_at.desc()).all()

    def generate():
        data = StringIO()
        writer = csv.writer(data)
        writer.writerow(['Fecha', 'Usuario', 'Modulo', 'Accion', 'Descripcion', 'Estatus'])
        yield data.getvalue()
        data.seek(0)
        data.truncate(0)

        for r in registros:
            fecha = r.created_at.strftime("%Y-%m-%d %I:%M %p") if r.created_at else "N/A"
            user_name = getattr(r.user, 'full_name', 'No registrado') if r.user else "No registrado"
            status = "Fallido" if "FALLIDO" in (r.action_type or "").upper() else "Completado"
            
            writer.writerow([fecha, user_name, r.module, r.action_type, r.description, status])
            yield data.getvalue()
            data.seek(0)
            data.truncate(0)

    headers = {
        "Content-Disposition": "attachment; filename=reporte_auditoria_sages.csv",
        "Content-Type": "text/csv; charset=utf-8"
    }
    return Response(generate(), headers=headers)