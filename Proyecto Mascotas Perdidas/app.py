#Importamos Flask
import os
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

ADMIN_USER = "admin"
ADMIN_PASS = "1234"

# Crear la instancia de Flask
app = Flask(__name__)

#Creamos una clave secreta
app.secret_key= "clave_secreta_segura"

# Definir la carpeta donde se guardarán las imágenes subidas
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Configuración de la base de datos SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mascotas.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Crear instancia de SQLAlchemy para manejar la base de datos
db = SQLAlchemy(app)

#Creamos el panel del usuario
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    rol = db.Column(db.String(10), default="usuario")  # "usuario" o "admin"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Definición del modelo Mascotas para la base de datos
class Mascotas(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # ID único para cada registro
    nombre_animal = db.Column(db.String(100), nullable=False)  # Nombre de la mascota
    descripcion_animal = db.Column(db.Text, nullable=True)  # Descripción de la mascota
    ubicacion_animal = db.Column(db.Text, nullable=True)  # Lugar donde se perdió
    contacto_animal = db.Column(db.String(20), nullable=True)  # Datos de contacto
    foto_animal = db.Column(db.String(100), nullable=True)  # Nombre del archivo de la foto
    estado_animal = db.Column(db.String(20), default="pendiente")  # pendiente, aceptado, rechazado
    motivo_rechazo = db.Column(db.Text, nullable=True)  # Solo si se rechaza
    aprobado = db.Column(db.Boolean, default=False)  # Aprobación del administrador
    user_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)  # Relación con usuario

# Crear las tablas en la base de datos (si no existen)
with app.app_context():
    db.create_all()

# Ruta principal que carga el index.html
@app.route("/")
def index():
    #Trae solo los reportes aprobados
    mascotas = Mascotas.query.filter_by(estado_animal="aprobado").all()
    return render_template("index.html", mascotas= mascotas)

# Ruta para mostrar y procesar el formulario de reporte
@app.route("/reportar", methods=["GET", "POST"])
def mostrar_reporte():
    mensaje = None # Definimos mensaje por defecto para evitar error
    if not session.get("user_id"):
        return redirect(url_for("login"))
    if request.method == "POST":
        # Obtener datos enviados desde el formulario
        nombre = request.form.get("nombre")
        descripcion = request.form.get("descripcion")
        ubicacion = request.form.get("ubicacion")
        contacto = request.form.get("contacto")
        foto = request.files.get("foto")

        filename = None  # Inicializar el nombre de archivo como None

        if foto:
            # Asegurar que el nombre del archivo sea seguro
            filename = secure_filename(foto.filename)

            # Obtener la carpeta de subida desde la configuración
            upload_folder = app.config['UPLOAD_FOLDER']

            # Crear la carpeta si no existe para evitar errores
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)

            # Guardar el archivo de la foto en la carpeta indicada
            foto.save(os.path.join(upload_folder, filename))

        # Crear un nuevo registro en la base de datos con los datos recibidos
        nuevo_reporte = Mascotas(
            nombre_animal=nombre,
            descripcion_animal=descripcion,
            ubicacion_animal=ubicacion,
            contacto_animal=contacto,
            foto_animal=filename,  # Guardar el nombre del archivo para referencia
            user_id=session.get("user_id")  # <-- Asignar el id del usuario logueado
            
        )

        # Agregar el nuevo registro a la sesión de la base de datos
        db.session.add(nuevo_reporte)

        # Confirmar los cambios y guardar en la base de datos
        db.session.commit()

        # Retornar mensaje de éxito (puedes cambiar esto por un redirect o render_template con mensaje)
        mensaje = "Reporte guardado con éxito"

    # Si es método GET, solo renderizar el formulario
    return render_template("reportar.html", mensaje= mensaje)

#Creamos la ruta de /LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        # Primero obtienes datos del formulario
        username = request.form.get("username")
        password = request.form.get("password")
        
        # Ahora chequeas si es el admin usando las constantes
        if username == ADMIN_USER and password == ADMIN_PASS:
            session["admin"] = True
            session["usuario"] = username  # Guardar usuario en sesión para mostrar nombre
            session["user_id"] = None  # Opcional: admin no tiene user_id
            return redirect(url_for("panel_admin"))

        usuario = Usuario.query.filter_by(username=username).first()
        if usuario and usuario.check_password(password):
            session["user_id"] = usuario.id
            session["usuario"] = usuario.username  # Guardar el username para mostrar en header
            session["rol"] = usuario.rol
            if usuario.rol == "admin":
                session["admin"] = True
                return redirect(url_for("panel_admin"))
            else:
                session.pop("admin", None)  # Asegurar que no tenga sesión admin
                return redirect(url_for("index"))
        else:
            error = "Usuario o contraseña incorrectos"

    
    # Para GET o si falla el login, renderizas la plantilla con error (o None)
    return render_template("login.html", error=error)


#Creamos el panel de administrador
@app.route("/admin")
def panel_admin():
    if not session.get("admin"):
        return redirect(url_for("login"))
    reportes_pendientes = Mascotas.query.filter_by(estado_animal="pendiente").all()
    return render_template("admin.html", mascotas=reportes_pendientes)

#Creamos la ruta de aprobar/rechazar reportes
@app.route("/aprobar/<int:id>", methods=["POST"])
def aprobar_reporte(id):
    if not session.get("admin"):
        return redirect(url_for("login"))
    mascota = Mascotas.query.get_or_404(id)
    mascota.estado_animal = "aprobado"
    mascota.motivo_rechazo = None
    db.session.commit()
    return redirect(url_for("panel_admin"))

@app.route("/rechazar/<int:id>", methods=["POST"])
def rechazar_reporte(id):
    if not session.get("admin"):
        return redirect(url_for("login"))
    mascota = Mascotas.query.get_or_404(id)
    
    motivo = request.form.get("motivo_rechazo", None)
    if not motivo or motivo.strip() == "":
        # Puedes manejar el error: motivo obligatorio
        # Por ejemplo, devolver un mensaje o redirigir con error
        return "El motivo de rechazo es obligatorio", 400
    
    mascota.estado_animal = "rechazado"
    mascota.motivo_rechazo = motivo.strip()
    
    db.session.commit()
    return redirect(url_for("panel_admin"))

#Panel de registro
@app.route("/registro", methods=["GET", "POST"])
def registro():
    mensaje = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Verificar si ya existe usuario
        if Usuario.query.filter_by(username=username).first():
            mensaje = "El nombre de usuario ya existe"
        else:
            nuevo_usuario = Usuario(username=username)
            nuevo_usuario.set_password(password)
            db.session.add(nuevo_usuario)
            db.session.commit()
            mensaje = "Registro exitoso, ahora inicia sesión"
    return render_template("registro.html", mensaje=mensaje)

#Para cerrar sesion
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

#Panel de mis reportes
@app.route("/mis_reportes")
def mis_reportes():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_id = session["user_id"]
    reportes = Mascotas.query.filter_by(user_id=user_id).filter(Mascotas.estado_animal != "encontrado").all()
    return render_template("mis_reportes.html", reportes=reportes)


#"Eliminar" reporte — marcar como encontrado
@app.route("/encontrado/<int:id>", methods=["POST"])
def marcar_encontrado(id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    reporte = Mascotas.query.get_or_404(id)
    if reporte.user_id != session["user_id"]:
        # Si el reporte no pertenece al usuario, denegamos acceso
        return "No autorizado", 403

    reporte.estado_animal = "encontrado"
    db.session.commit()
    return redirect(url_for("mis_reportes"))

#Ruta para editar reporte (formulario y guardar cambios)
@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar_reporte(id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    reporte = Mascotas.query.get_or_404(id)
    if reporte.user_id != session["user_id"]:
        return "No autorizado", 403

    if request.method == "POST":
        reporte.nombre_animal = request.form.get("nombre")
        reporte.descripcion_animal = request.form.get("descripcion")
        reporte.ubicacion_animal = request.form.get("ubicacion")
        reporte.contacto_animal = request.form.get("contacto")

        # Manejar cambio de foto
        if "foto" in request.files and request.files["foto"].filename != "":
            nueva_foto = request.files["foto"]
            nombre_archivo = secure_filename(nueva_foto.filename)
            nueva_foto.save(os.path.join(app.config["UPLOAD_FOLDER"], nombre_archivo))
            reporte.foto_animal = nombre_archivo  # Reemplaza por la nueva
        
        # --- Sincronizar estados: vuelve a revisión por admin ---
        reporte.estado_animal = "pendiente"  # cadena usada en tu admin/index
        reporte.aprobado = False

        db.session.commit()
        return redirect(url_for("mis_reportes"))

    return render_template("editar_reporte.html", reporte=reporte)

@app.route('/sobre_nosotros')
def sobre_nosotros():
    return render_template('sobre_nosotros.html')

@app.route('/preguntas_frecuentes')
def preguntas_frecuentes():
    return render_template('preguntas_frecuentes.html')

@app.route('/politica_privacidad')
def politica_privacidad():
    return render_template('politica_privacidad.html')

@app.route('/terminos_de_uso')
def terminos_de_uso():
    return render_template('terminos_de_uso.html')







# Ejecutar la aplicación en modo debug
if __name__ == "__main__":
    app.run(debug=True)
