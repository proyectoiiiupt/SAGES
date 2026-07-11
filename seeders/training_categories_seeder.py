from app.extensions import db
from app.models.training_category_model import TrainingCategory

def seed_training_categories():
    if TrainingCategory.query.count() > 0:
        print("Training categories already seeded.")
        return

    categories_data = [
        {"category_code": "TCAT-001", "name": "Taller"},
        {"category_code": "TCAT-002", "name": "Conversatorio"},
        {"category_code": "TCAT-003", "name": "Charla"},
        {"category_code": "TCAT-004", "name": "Congreso"},
        {"category_code": "TCAT-005", "name": "Asamblea"},
        {"category_code": "TCAT-006", "name": "Seminario"},
        {"category_code": "TCAT-007", "name": "Foro"}
    ]

    for data in categories_data:
        category = TrainingCategory(**data)
        db.session.add(category)
    
    db.session.commit()
    print("Training categories seeded successfully.")