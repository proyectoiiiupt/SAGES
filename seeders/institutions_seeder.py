from app.extensions import db
from app.models.institution_model import Institution
from app.models.institution_type_model import InstitutionType
from app.models.institution_scope_model import InstitutionScope
from app.models.institution_dependency_model import InstitutionDependency
from app.models.parish_model import Parish
from app.models.status_model import Status

def seed_institutions():
    if Institution.query.count() > 0:
        print("Institutions already seeded.")
        return

    institutions_data = [
        {
            "institution_code": "EDU-001",
            "institution_type_code": "INST-001", # Universidad
            "institution_name": "Universidad Central de Venezuela (UCV)",
            "plantel_code": "DEA-U0001",
            "institution_scope_code": "SCOP-001", # Público
            "institution_dependency_code": "DEP-008", # Autónoma
            "parish_code": "PAR-1134", # San Pedro
            "address": "Ciudad Universitaria de Caracas, Los Chaguaramos.",
            "phone": "02126050000",
            "status_code": "STAT-001" # Activo
        },
        {
            "institution_code": "EDU-002",
            "institution_type_code": "INST-001", # Universidad
            "institution_name": "Universidad Católica Andrés Bello (UCAB)",
            "plantel_code": "DEA-U0002",
            "institution_scope_code": "SCOP-002", # Privado
            "institution_dependency_code": "DEP-001", # Nacional (Supervisión MPPEU)
            "parish_code": "PAR-1118", # Antímano
            "address": "Av. Teherán, Montalbán.",
            "phone": "02124072000",
            "status_code": "STAT-001"
        },
        {
            "institution_code": "EDU-003",
            "institution_type_code": "INST-003", # Liceo / Educación Media
            "institution_name": "Liceo de Aplicación",
            "plantel_code": "OD00010101",
            "institution_scope_code": "SCOP-001", # Público
            "institution_dependency_code": "DEP-001", # Nacional
            "parish_code": "PAR-1123", # El Paraíso
            "address": "Av. Páez, frente a la Plaza Washington.",
            "phone": "02124820011",
            "status_code": "STAT-001"
        },
        {
            "institution_code": "EDU-004",
            "institution_type_code": "INST-006", # Complejo Educativo Integral
            "institution_name": "Colegio La Salle Tienda Honda",
            "plantel_code": "PD00020101",
            "institution_scope_code": "SCOP-002", # Privado
            "institution_dependency_code": "DEP-001", # Nacional (Supervisión MPPE)
            "parish_code": "PAR-1117", # Altagracia
            "address": "Esquina de Tienda Honda a Santa Bárbara.",
            "phone": "02128611122",
            "status_code": "STAT-001"
        },
        {
            "institution_code": "EDU-005",
            "institution_type_code": "INST-003", # Liceo / Educación Media
            "institution_name": "Escuela Técnica Industrial (E.T.I.) José de San Martín",
            "plantel_code": "OD00030101",
            "institution_scope_code": "SCOP-001", # Público
            "institution_dependency_code": "DEP-001", # Nacional
            "parish_code": "PAR-1123", # El Paraíso
            "address": "Av. San Martín, cruce con calle La Paz.",
            "phone": "02124512233",
            "status_code": "STAT-001"
        },
        {
            "institution_code": "EDU-006",
            "institution_type_code": "INST-006", # Complejo Educativo Integral
            "institution_name": "U.E. Colegio Fe y Alegría La Rinconada",
            "plantel_code": "PD00040101",
            "institution_scope_code": "SCOP-003", # Mixto / Subvencionado
            "institution_dependency_code": "DEP-004", # Subvencionada / Convenio MPPE
            "parish_code": "PAR-1121", # Coche
            "address": "Sector La Rinconada, adyacente al Hipódromo.",
            "phone": "02126813344",
            "status_code": "STAT-001"
        },
        {
            "institution_code": "EDU-007",
            "institution_type_code": "INST-004", # Escuela Básica / Primaria
            "institution_name": "U.E. Municipal Andrés Eloy Blanco",
            "plantel_code": "MD00050101",
            "institution_scope_code": "SCOP-001", # Público
            "institution_dependency_code": "DEP-003", # Municipal
            "parish_code": "PAR-1128", # La Vega
            "address": "Bulevar de La Vega, calle principal.",
            "phone": "02124724455",
            "status_code": "STAT-001"
        },
        {
            "institution_code": "EDU-008",
            "institution_type_code": "INST-002", # Instituto Universitario
            "institution_name": "Instituto Universitario de Tecnología Antonio José de Sucre",
            "plantel_code": "DEA-I0008",
            "institution_scope_code": "SCOP-002", # Privado
            "institution_dependency_code": "DEP-001", # Nacional (Supervisión)
            "parish_code": "PAR-1124", # El Recreo
            "address": "Av. Casanova, Sabana Grande.",
            "phone": "02127625566",
            "status_code": "STAT-001"
        },
        {
            "institution_code": "EDU-009",
            "institution_type_code": "INST-005", # Centro de Formación Técnica y Laboral
            "institution_name": "Centro de Capacitación y Oficios San Juan Bosco",
            "plantel_code": "CD00090101",
            "institution_scope_code": "SCOP-004", # Comunitario / Popular
            "institution_dependency_code": "DEP-004", # Subvencionada
            "parish_code": "PAR-1138", # 23 de enero
            "address": "Bloque 7, Zona F, 23 de Enero.",
            "phone": "02128586677",
            "status_code": "STAT-001"
        },
        {
            "institution_code": "EDU-010",
            "institution_type_code": "INST-004", # Escuela Básica / Primaria
            "institution_name": "U.E. Distrital Juan Antonio Pérez Bonalde",
            "plantel_code": "ED00100101",
            "institution_scope_code": "SCOP-001", # Público
            "institution_dependency_code": "DEP-002", # Estadal (Gobierno del Distrito Capital)
            "parish_code": "PAR-1125", # El Valle
            "address": "Calle 14 de Los Jardines del Valle.",
            "phone": "02126717788",
            "status_code": "STAT-001"
        },
        {
            "institution_code": "EDU-011",
            "institution_type_code": "INST-003", # Liceo / Educación Media
            "institution_name": "Liceo Andrés Bello",
            "plantel_code": "OD00110101",
            "institution_scope_code": "SCOP-001", # Público
            "institution_dependency_code": "DEP-001", # Nacional
            "parish_code": "PAR-1126", # La Candelaria
            "address": "Av. México, frente a la Galería de Arte Nacional.",
            "phone": "02125718899",
            "status_code": "STAT-001"
        }
    ]

    for data in institutions_data:
        type_code = data.pop("institution_type_code")
        scope_code = data.pop("institution_scope_code")
        dependency_code = data.pop("institution_dependency_code")
        parish_code = data.pop("parish_code")
        status_code = data.pop("status_code")

        inst_type = InstitutionType.query.filter_by(institution_type_code=type_code).first()
        inst_scope = InstitutionScope.query.filter_by(scope_code=scope_code).first()
        inst_dep = InstitutionDependency.query.filter_by(dependency_code=dependency_code).first()
        parish = Parish.query.filter_by(parish_code=parish_code).first()
        status = Status.query.filter_by(status_code=status_code).first()

        if not inst_type:
            print(f"Error: Tipo de institución '{type_code}' no encontrado.")
            return
        if not inst_scope:
            print(f"Error: Sector/Scope '{scope_code}' no encontrado.")
            return
        if not inst_dep:
            print(f"Error: Dependencia '{dependency_code}' no encontrada.")
            return
        if not parish:
            print(f"Error: Parroquia '{parish_code}' no encontrada. ¿Corriste el seeder de parroquias?")
            return
        if not status:
            print(f"Error: Estatus '{status_code}' no encontrado.")
            return

        data["institution_type_id"] = inst_type.id
        data["institution_scope_id"] = inst_scope.id
        data["institution_dependency_id"] = inst_dep.id
        data["parish_id"] = parish.id
        data["status_id"] = status.id

        institution = Institution(**data)
        db.session.add(institution)
    
    db.session.commit()
    print("Institutions seeded successfully.")