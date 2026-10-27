from datetime import datetime, timezone
from app.extensions import db
from app.models.binnacle_model import Binnacle
from app.binnacle.types import AuditModule, AuditAction, AuditStatus


def seed_backup_log():
    """
    Inserta un registro inicial de respaldo automatizado exitoso en sages.binnacle.
    """
    if Binnacle.query.filter_by(action_type=AuditAction.RESPALDO_AUTOMATICO_EXITOSO.value).first():
        print("Backup logs already seeded.")
        return

    log = Binnacle(
        module=AuditModule.CONFIGURATIONS.value,
        action_type=AuditAction.RESPALDO_AUTOMATICO_EXITOSO.value,
        description="Volcado de seguridad automatizado ejecutado por tarea Cron del servidor",
        status=AuditStatus.COMPLETADO.value,
        ip_address="127.0.0.1",
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(log)
    db.session.commit()
    print("Backup log seeded successfully.")


if __name__ == '__main__':
    import os
    import sys
    import dotenv

    # Cargar variables de entorno y ruta raíz para ejecución CLI independiente
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    sys.path.insert(0, root_dir)
    dotenv.load_dotenv(os.path.join(root_dir, '.env'))

    from app import create_app
    from app.configurations.services import get_last_backup_log

    app = create_app()
    with app.app_context():
        command = sys.argv[1].lower() if len(sys.argv) > 1 else 'status'
        if command == 'seed':
            seed_backup_log()
        elif command == 'status':
            last = get_last_backup_log()
            if last:
                print(f"[INFO] Último respaldo activo:")
                print(f"       - ID: {last.id}")
                print(f"       - Fecha UTC: {last.created_at}")
                print(f"       - Módulo: {last.module}")
                print(f"       - Acción: {last.action_type}")
                print(f"       - Estado: {last.status}")
                print(f"       - Descripción: {last.description}")
            else:
                print("[INFO] No hay respaldos registrados en la bitácora (Estado por defecto 'Sin respaldos registrados').")
        else:
            print("Uso: python seeders/backup_logs_seeder.py [seed|status]")
