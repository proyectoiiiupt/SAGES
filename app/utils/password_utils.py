from app.extensions import db, bcrypt

def change_user_password(user, new_password):
    """
    Actualiza la contraseña del usuario de forma segura usando Flask-Bcrypt.
    Genera el hash bcrypt de la nueva contraseña y guarda los cambios en la base de datos.
    """
    user.password = bcrypt.generate_password_hash(new_password).decode('utf-8')
    db.session.add(user)
    db.session.commit()
    return True
