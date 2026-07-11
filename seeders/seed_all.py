import os
import sys

# Agregar el directorio raíz del proyecto al sys.path para poder importar 'app'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db

# Importar todos los seeders
from seeders.status_seeder import seed_status
from seeders.roles_seeder import seed_roles
from seeders.permissions_seeder import seed_permissions
from seeders.states_seeder import seed_states
from seeders.companies_seeder import seed_companies
from seeders.educational_levels_seeder import seed_educational_levels
from seeders.institution_dependencies_seeder import seed_institution_dependencies
from seeders.institution_scopes_seeder import seed_institution_scopes
from seeders.institution_types_seeder import seed_institution_types
from seeders.positions_seeder import seed_positions
from seeders.reasons_seeder import seed_reasons
from seeders.training_categories_seeder import seed_training_categories
from seeders.persons_seeder import seed_persons
from seeders.trainings_seeder import seed_trainings
from seeders.municipalities_seeder import seed_municipalities
from seeders.cities_seeder import seed_cities
from seeders.permission_roles_seeder import seed_permission_roles
from seeders.users_seeder import seed_users
from seeders.role_users_seeder import seed_role_users
from seeders.parishes_seeder import seed_parishes
from seeders.locations_seeder import seed_locations
from seeders.places_seeder import seed_places
from seeders.institutions_seeder import seed_institutions
from seeders.institution_levels_seeder import seed_institution_levels
from seeders.institutional_staff_seeder import seed_institutional_staff
from seeders.company_staff_seeder import seed_company_staff

def run_all_seeders():
    print("Iniciando proceso de seeding...")
    app = create_app()
    with app.app_context():
        try:
            # 1. Tablas independientes / Catálogos base
            seed_status()
            seed_roles()
            seed_permissions()
            seed_states()
            seed_companies()
            seed_educational_levels()
            seed_institution_dependencies()
            seed_institution_scopes()
            seed_institution_types()
            seed_positions()
            seed_reasons()
            seed_training_categories()
            seed_persons()

            # 2. Tablas con dependencias de nivel 1
            seed_trainings()           # Depende de training_categories, status
            seed_municipalities()      # Depende de states
            seed_cities()              # Depende de states
            seed_permission_roles()    # Depende de roles, permissions
            seed_users()               # Depende de persons, status

            # 3. Tablas con dependencias de nivel 2
            seed_role_users()          # Depende de users, roles
            seed_parishes()            # Depende de municipalities

            # 4. Tablas con dependencias de nivel 3
            seed_locations()           # Depende de cities, parishes
            seed_places()              # Depende de companies, parishes, status
            seed_institutions()        # Depende de institution_types, institution_scopes, institution_dependencies, parishes, status

            # 5. Tablas con dependencias de nivel 4
            seed_institution_levels()  # Depende de institutions, educational_levels
            seed_institutional_staff() # Depende de institutions, persons, positions
            seed_company_staff()       # Depende de places, persons, positions

            print("¡Todos los seeders se han ejecutado correctamente!")
        except Exception as e:
            db.session.rollback()
            print(f"Error durante el seeding: {str(e)}")
            print("Se ha hecho rollback de las transacciones.")

if __name__ == "__main__":
    run_all_seeders()
