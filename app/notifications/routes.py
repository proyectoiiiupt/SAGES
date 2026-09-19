from flask import jsonify, request, render_template, abort, session
from flask_login import login_required, current_user
from app.extensions import db
from app.models.notification_model import Notification
from app.notifications import notifications_bp
from datetime import datetime, timezone

@notifications_bp.route('/api/unread-count', methods=['GET'])
@login_required
def api_unread_count():
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({"unread_count": count})

@notifications_bp.route('/api/dropdown', methods=['GET'])
@login_required
def api_dropdown():
    limit = request.args.get('limit', 3, type=int)
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).limit(limit).all()
    
    data = []
    for notif in notifications:
        data.append({
            "id": notif.id,
            "title": notif.title,
            "message": notif.message,
            "type": notif.type,
            "is_read": notif.is_read,
            "created_at": notif.created_at.isoformat(),
            "redirect_url": notif.redirect_url,
            "action_text": notif.action_text,
            "extra_data": notif.extra_data
        })
    return jsonify({"notifications": data})

@notifications_bp.route('/api/<int:id>/read', methods=['POST'])
@login_required
def api_mark_read(id):
    # Anti-IDOR: isolation by current_user.id
    notification = Notification.query.filter_by(id=id, user_id=current_user.id).first()
    if not notification:
        abort(404)
        
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        db.session.commit()
        
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({"success": True, "unread_count": unread_count})

@notifications_bp.route('/api/mark-all-read', methods=['POST'])
@login_required
def api_mark_all_read():
    now = datetime.now(timezone.utc)
    
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update(
        {Notification.is_read: True, Notification.read_at: now},
        synchronize_session=False
    )
    db.session.commit()
    
    return jsonify({"success": True, "unread_count": 0})

@notifications_bp.route('/history', methods=['GET'])
@login_required
def history():
    page = request.args.get('page', 1, type=int)
    filter_type = request.args.get('filter', 'all')
    
    # Store the actual referrer if it's outside the notifications module
    ref = request.referrer
    if ref and '/notifications/history' not in ref:
        session['notif_return_url'] = ref
        
    back_url = session.get('notif_return_url')
    
    query = Notification.query.filter_by(user_id=current_user.id)
    
    if filter_type == 'unread':
        query = query.filter_by(is_read=False)
    elif filter_type == 'critical':
        query = query.filter(Notification.type.in_(['WARNING', 'DANGER']))
        
    pagination = query.order_by(Notification.created_at.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    
    return render_template('notifications/index.html', pagination=pagination, current_filter=filter_type, back_url=back_url)
