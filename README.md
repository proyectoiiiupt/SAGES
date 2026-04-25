# Sistema Automatizaddo de Gestión de Solicitudes de Servicios Formacion Comunitaria UREE (CORPOELEC)

Sistema profesional para la gestión de solicitudes de formación comunitaria en el área de Uso Racional y Eficiente de la Energía.

## 🛠️ Tecnologías
- **Backend:** Python / Flask
- **Base de Datos:** PostgreSQL
- **Frontend:** Jinja2 (HTML5, CSS3, JS)
- **Arquitectura:** Modular (Application Factory + Blueprints)

## 📂 Estructura del Proyecto
El proyecto sigue una organización por **features** (módulos), permitiendo que cada funcionalidad (Autenticación, Usuarios, Solicitudes) sea independiente y escalable.

## 🚀 Instalación rápida
1. Clonar repositorio: `git clone [url-aqui]`
2. Crear entorno virtual: `py -m venv venv`
3. Activar entorno: `.\venv\Scripts\Activate.ps1` (Windows)
4. Instalar librerías: `pip install -r requirements.txt`
5. Configurar `.env` con tus datos de base de datos.
6. Ejecutar: `python run.py`

## 🚀 Siempre antes de Comenzar a Trabajar y hacer algun cambio
1. Traer Cambios a  Entorno Local: `git pull origin main`

## 🚀 NO EDITAR Archivos de Importancia, solo agregar
1. requirements.txt

## 🚀 Para subir los cambios
1. Siempre lanzar un status de git: `git status`
2. Agregar los archivos a subir: `git add ej:ruta/archivo`
3. Commitear (informacion del commit): `git commit -m ""`
4. Pushear (Subir): `git push`

## 🚀 Actualizar a sus entornos personales
1. Verificar que cuenta de correo esta asociada: `git config user.email`
2. configurar a tu usuario personal: `git config --local user.name "Tu Nombre Real o de GitHub"`
3. configurar a correo personal: `git config --local user.email "el_correo_de_tu_cuenta_personal@ejemplo.com"`
4. Verificar actualizacion de cuenta: `git config user.email`
