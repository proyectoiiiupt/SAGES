from app.extensions import db
from app.models.institution_dependency_model import InstitutionDependency

def seed_institution_dependencies():
    if InstitutionDependency.query.count() > 0:
        print("Institution dependencies already seeded.")
        return

    dependencies = [
        {
            "dependency_code": "DEP-001",
            "name": "Nacional",
            "description": "Instituciones públicas financiadas, administradas y supervisadas directamente por el Ejecutivo Nacional a través del Ministerio del Poder Popular para la Educación (MPPE) o el Ministerio de Educación Universitaria."
        },
        {
            "dependency_code": "DEP-002",
            "name": "Estadal",
            "description": "Planteles públicos que dependen técnica, presupuestaria y administrativamente del Ejecutivo Regional, gestionados mediante las Secretarías de Educación de las Gobernaciones de cada estado."
        },
        {
            "dependency_code": "DEP-003",
            "name": "Municipal",
            "description": "Unidades educativas locales creadas y financiadas por los gobiernos municipales, bajo la coordinación directa de las Direcciones de Educación de las Alcaldías."
        },
        {
            "dependency_code": "DEP-004",
            "name": "Subvencionada / Convenio MPPE",
            "description": "Planteles de administración privada o comunitaria sin fines de lucro que operan mediante subsidios parciales o totales del Estado venezolano (ej. Asociación Venezolana de Educación Católica - AVEC, Fe y Alegría, etc.)."
        },
        {
            "dependency_code": "DEP-005",
            "name": "Centralizadas",
            "description": "No tienen personalidad jurídica ni patrimonio propio. Actúan directamente bajo las órdenes del órgano central (como un ministerio)."
        },
        {
            "dependency_code": "DEP-006",
            "name": "Descentralizadas",
            "description": "Tienen personalidad jurídica y patrimonio propio, creadas por ley para cumplir una función específica. Aunque reportan a un ministerio o entidad superior, gozan de autonomía para gestionar sus recursos y decisiones."
        },
        {
            "dependency_code": "DEP-007",
            "name": "Deconcentradas",
            "description": "Son órganos que pertenecen a la estructura centralizada, pero a los que se les asignan competencias exclusivas o una sede geográfica distinta para agilizar trámites, aunque carecen de autonomía financiera real."
        },
        {
            "dependency_code": "DEP-008",
            "name": "Autónoma",
            "description": "Instituciones públicas que poseen personalidad jurídica y patrimonio propio, gozando de autonomía organizativa y académica consagrada por las leyes (común en universidades nacionales tradicionales)."
        }
    ]

    # Inserción en la base de datos siguiendo la estructura limpia
    for data in dependencies:
        dependency = InstitutionDependency(**data)
        db.session.add(dependency)
        
    db.session.commit()
    print("Institution dependencies seeded successfully.")