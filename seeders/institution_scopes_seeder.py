from app.extensions import db
from app.models.institution_scope_model import InstitutionScope

def seed_institution_scopes():
    if InstitutionScope.query.count() > 0:
        print("Institution scopes already seeded.")
        return

    scopes = [
        {
            "scope_code": "SCOP-001",
            "name": "Público",
            "description": "Instituciones de financiamiento y administración totalmente estatal. El acceso es gratuito y está regulado de forma directa por los órganos del Estado venezolano."
        },
        {
            "scope_code": "SCOP-002",
            "name": "Privado",
            "description": "Instituciones particulares financiadas de forma autónoma mediante matrículas y mensualidades pagadas por los representantes, operando bajo la supervisión pedagógica del ministerio."
        },
        {
            "scope_code": "SCOP-003",
            "name": "Mixto / Subvencionado",
            "description": "Sector de co-gestión o convenio. La administración es privada, pero cuenta con subsidio o financiamiento parcial del Estado para sostener la nómina."
        },
        {
            "scope_code": "SCOP-004",
            "name": "Comunitario / Popular",
            "description": "Espacios y centros de formación alternativa gestionados por organizaciones de base, consejos comunales o movimientos sociales dirigidos al desarrollo socioproductivo local."
        }
    ]

    for data in scopes:
        scope = InstitutionScope(**data)
        db.session.add(scope)
        
    db.session.commit()
    print("Institution scopes seeded successfully.")