from app.extensions import db
from app.models.person_model import Person

def seed_persons():
    if Person.query.count() > 0:
        print("Persons already seeded.")
        return

    persons = [
        {
            "person_code": "PERS-001", "identification_type": "V", "identification_number": "30307235",
            "first_name": "Moises", "second_name": "Daniel", "last_name": "Hernandez", "middle_name": "Diaz",
            "email": "moisesdhernandez3@gmail.com", "mobile": "04141112233", "phone": "02121112233"
        },
        {
            "person_code": "PERS-002", "identification_type": "V", "identification_number": "30990735",
            "first_name": "Willangelo", "second_name": "Giosue", "last_name": "Parra", "middle_name": "Pulido",
            "email": "willangeloparra16@gmail.com", "mobile": "04249990011", "phone": "02419990011"
        },
        {
            "person_code": "PERS-003", "identification_type": "V", "identification_number": "31794116",
            "first_name": "Ivor", "second_name": "Alexander", "last_name": "Quintero", "middle_name": "Lopez",
            "email": "ivorquinte20@gmail.com", "mobile": "04124445566", "phone": "02124445566"
        },
        {
            "person_code": "PERS-004", "identification_type": "V", "identification_number": "31052298",
            "first_name": "Gerardo", "second_name": "David", "last_name": "Paredes", "middle_name": "Lovera",
            "email": "paredesdavid302@gmail.com", "mobile": "04167778899", "phone": "02417778899"
        },
        {
            "person_code": "PERS-005", "identification_type": "V", "identification_number": "28456123",
            "first_name": "Elias", "second_name": "Alejandro", "last_name": "Silva", "middle_name": "Rojas",
            "email": "elias.silva.dev@gmail.com", "mobile": "04145551234", "phone": "02125551234"
        },
        {
            "person_code": "PERS-006", "identification_type": "V", "identification_number": "26123456",
            "first_name": "Maria", "second_name": "Alejandra", "last_name": "Garcia", "middle_name": "Perez",
            "email": "magarcia26@gmail.com", "mobile": "04128889900", "phone": "02128889900"
        },
        {
            "person_code": "PERS-007", "identification_type": "V", "identification_number": "27890123",
            "first_name": "Luis", "second_name": "Fernando", "last_name": "Romero", "middle_name": "Martinez",
            "email": "lfromero.tech@gmail.com", "mobile": "04242223344", "phone": "02122223344"
        },
        {
            "person_code": "PERS-008", "identification_type": "V", "identification_number": "29345678",
            "first_name": "Ana", "second_name": "Karina", "last_name": "Torres", "middle_name": "Ruiz",
            "email": "anakt.ruiz@gmail.com", "mobile": "04166667788", "phone": "02416667788"
        },
        {
            "person_code": "PERS-009", "identification_type": "V", "identification_number": "25678901",
            "first_name": "Carlos", "second_name": "Eduardo", "last_name": "Mendez", "middle_name": "Vargas",
            "email": "cemendez89@gmail.com", "mobile": "04143334455", "phone": "02123334455"
        },
        {
            "person_code": "PERS-010", "identification_type": "V", "identification_number": "30123456",
            "first_name": "Sofia", "second_name": "Valentina", "last_name": "Blanco", "middle_name": "Herrera",
            "email": "sofia.blanco.h@gmail.com", "mobile": "04121119988", "phone": "02121119988"
        },
        {
            "person_code": "PERS-011", "identification_type": "V", "identification_number": "24567890",
            "first_name": "Jose", "second_name": "Antonio", "last_name": "Castro", "middle_name": "Diaz",
            "email": "jacastro.admin@gmail.com", "mobile": "04247776655", "phone": "02417776655"
        }
    ]

    for data in persons:
        person = Person(**data)
        db.session.add(person)
    
    db.session.commit()
    print("Persons seeded successfully.")