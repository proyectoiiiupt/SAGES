from app.extensions import db
from app.models.state_model import State

def seed_states():
    if State.query.count() > 0:
        print("States already seeded.")
        return

    states = [
        {"state_code": "ST-001", "name": "Amazonas"},
        {"state_code": "ST-002", "name": "Anzoátegui"},
        {"state_code": "ST-003", "name": "Apure"},
        {"state_code": "ST-004", "name": "Aragua"},
        {"state_code": "ST-005", "name": "Barinas"},
        {"state_code": "ST-006", "name": "Bolívar"},
        {"state_code": "ST-007", "name": "Carabobo"},
        {"state_code": "ST-008", "name": "Cojedes"},
        {"state_code": "ST-009", "name": "Delta Amacuro"},
        {"state_code": "ST-010", "name": "Falcón"},
        {"state_code": "ST-011", "name": "Guárico"},
        {"state_code": "ST-012", "name": "Lara"},
        {"state_code": "ST-013", "name": "Mérida"},
        {"state_code": "ST-014", "name": "Miranda"},
        {"state_code": "ST-015", "name": "Monagas"},
        {"state_code": "ST-016", "name": "Nueva Esparta"},
        {"state_code": "ST-017", "name": "Portuguesa"},
        {"state_code": "ST-018", "name": "Sucre"},
        {"state_code": "ST-019", "name": "Táchira"},
        {"state_code": "ST-020", "name": "Trujillo"},
        {"state_code": "ST-021", "name": "La Guaira"},
        {"state_code": "ST-022", "name": "Yaracuy"},
        {"state_code": "ST-023", "name": "Zulia"},
        {"state_code": "ST-024", "name": "Distrito Capital"},
        {"state_code": "ST-025", "name": "Dependencias Federales"},
        {"state_code": "ST-026", "name": "Guayana Esequiba"}
    ] 

    for data in states:
        state = State(**data)
        db.session.add(state)
    
    db.session.commit()
    print("States seeded successfully.")
