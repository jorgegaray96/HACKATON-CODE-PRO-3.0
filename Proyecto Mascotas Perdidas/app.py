# Importamos módulos necesarios
import os  # Para manejar rutas y archivos
from flask import Flask, render_template, request, redirect, url_for, session
# Flask: framework web
# render_template: renderiza plantillas HTML
# request: accede a datos de formularios
# redirect: redirige a otra ruta
# url_for: genera URLs dinámicamente
# session: gestiona la sesión del usuario
from flask_sqlalchemy import SQLAlchemy  # ORM para base de datos SQLite
from werkzeug.utils import secure_filename  # Asegura nombres de archivos subidos
from werkzeug.security import generate_password_hash, check_password_hash
# Para almacenar y verificar contraseñas de forma segura

# Constantes para usuario admin
ADMIN_USER = "admin"
ADMIN_PASS = "1234"  # En producción, poner contraseña segura

# Crear instancia de Flask
app = Flask(__name__)

# Clave secreta para sesiones
app.secret_key = "clave_secreta_segura"

# Carpeta para almacenar imágenes subidas
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Configuración de la base de datos SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mascotas.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Evita advertencias

# Crear instancia de SQLAlchemy
db = SQLAlchemy(app)

# Modelo de usuarios
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # ID autoincremental
    username = db.Column(db.String(80), unique=True, nullable=False)  # Nombre de usuario único
    password_hash = db.Column(db.String(128), nullable=False)  # Contraseña en hash
    rol = db.Column(db.String(10), default="usuario")  # Rol: usuario o admin

    # Función para guardar contraseña de forma segura
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    # Función para verificar contraseña
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Modelo de mascotas/reportes
class Mascotas(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # ID único
    nombre_animal = db.Column(db.String(100), nullable=False)  # Nombre de la mascota
    descripcion_animal = db.Column(db.Text, nullable=True)  # Descripción opcional
    ubicacion_animal = db.Column(db.Text, nullable=True)  # Ubicación donde se perdió
    contacto_animal = db.Column(db.String(20), nullable=True)  # Contacto del dueño
    foto_animal = db.Column(db.String(100), nullable=True)  # Nombre de archivo de la foto
    estado_animal = db.Column(db.String(20), default="pendiente")  # Estado: pendiente, aprobado, rechazado
    motivo_rechazo = db.Column(db.Text, nullable=True)  # Solo si fue rechazado
    aprobado = db.Column(db.Boolean, default=False)  # Flag de aprobación admin
    user_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)  # Relación con usuario

# Crear tablas en la base de datos si no existen
with app.app_context():
    db.create_all()

# Ruta principal que muestra reportes aprobados
@app.route("/")
def index():
    mascotas = Mascotas.query.filter_by(estado_animal="aprobado").all()  # Solo aprobados
    return render_template("index.html", mascotas=mascotas)

# Ruta para reportar mascotas
@app.route("/reportar", methods=["GET", "POST"])
def mostrar_reporte():
    mensaje = None  # Inicializamos mensaje

    # Si no hay usuario logueado, redirige al login
    if not session.get("user_id"):
        return redirect(url_for("login"))

    # Procesar formulario POST
    if request.method == "POST":
        nombre = request.form.get("nombre")
        descripcion = request.form.get("descripcion")
        ubicacion = request.form.get("ubicacion")
        contacto = request.form.get("contacto")
        foto = request.files.get("foto")  # Archivo subido

        filename = None

        if foto:
            filename = secure_filename(foto.filename)  # Asegura el nombre
            upload_folder = app.config['UPLOAD_FOLDER']
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)  # Crea carpeta si no existe
            foto.save(os.path.join(upload_folder, filename))  # Guardar archivo

        # Crear nuevo registro
        nuevo_reporte = Mascotas(
            nombre_animal=nombre,
            descripcion_animal=descripcion,
            ubicacion_animal=ubicacion,
            contacto_animal=contacto,
            foto_animal=filename,
            user_id=session.get("user_id")  # ID del usuario logueado
        )
        db.session.add(nuevo_reporte)  # Agregar a la sesión
        db.session.commit()  # Guardar cambios
        mensaje = "Reporte guardado con éxito"

    return render_template("reportar.html", mensaje=mensaje)

# Ruta de login
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Login de admin
        if username == ADMIN_USER and password == ADMIN_PASS:
            session["admin"] = True
            session["usuario"] = username
            session["user_id"] = None
            return redirect(url_for("panel_admin"))

        # Login de usuario normal
        usuario = Usuario.query.filter_by(username=username).first()
        if usuario and usuario.check_password(password):
            session["user_id"] = usuario.id
            session["usuario"] = usuario.username
            session["rol"] = usuario.rol
            if usuario.rol == "admin":
                session["admin"] = True
                return redirect(url_for("panel_admin"))
            else:
                session.pop("admin", None)
                return redirect(url_for("index"))
        else:
            error = "Usuario o contraseña incorrectos"

    return render_template("login.html", error=error)

# Panel de administración
@app.route("/admin")
def panel_admin():
    if not session.get("admin"):
        return redirect(url_for("login"))
    reportes_pendientes = Mascotas.query.filter_by(estado_animal="pendiente").all()
    return render_template("admin.html", mascotas=reportes_pendientes)

# Aprobar reporte
@app.route("/aprobar/<int:id>", methods=["POST"])
def aprobar_reporte(id):
    if not session.get("admin"):
        return redirect(url_for("login"))
    mascota = Mascotas.query.get_or_404(id)
    mascota.estado_animal = "aprobado"
    mascota.motivo_rechazo = None
    db.session.commit()
    return redirect(url_for("panel_admin"))

# Rechazar reporte
@app.route("/rechazar/<int:id>", methods=["POST"])
def rechazar_reporte(id):
    if not session.get("admin"):
        return redirect(url_for("login"))
    mascota = Mascotas.query.get_or_404(id)

    motivo = request.form.get("motivo_rechazo", None)
    if not motivo or motivo.strip() == "":
        return "El motivo de rechazo es obligatorio", 400

    mascota.estado_animal = "rechazado"
    mascota.motivo_rechazo = motivo.strip()
    db.session.commit()
    return redirect(url_for("panel_admin"))

# Registro de usuarios
@app.route("/registro", methods=["GET", "POST"])
def registro():
    mensaje = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Verificar si usuario existe
        if Usuario.query.filter_by(username=username).first():
            mensaje = "El nombre de usuario ya existe"
        else:
            nuevo_usuario = Usuario(username=username)
            nuevo_usuario.set_password(password)
            db.session.add(nuevo_usuario)
            db.session.commit()
            mensaje = "Registro exitoso, ahora inicia sesión"
    return render_template("registro.html", mensaje=mensaje)

# Cerrar sesión
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# Mis reportes
@app.route("/mis_reportes")
def mis_reportes():
    if "user_id" not in session:
        return redirect(url_for("login"))
    reportes = Mascotas.query.filter_by(user_id=session["user_id"]).order_by(Mascotas.id.desc()).all()
    return render_template("mis_reportes.html", reportes=reportes)

# Marcar reporte como encontrado
@app.route("/encontrado/<int:id>", methods=["POST"])
def marcar_encontrado(id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    reporte = Mascotas.query.get_or_404(id)
    if reporte.user_id != session["user_id"]:
        return "No autorizado", 403

    reporte.estado_animal = "encontrado"
    db.session.commit()
    return redirect(url_for("mis_reportes"))

# Editar reporte
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

        # Cambio de foto
        if "foto" in request.files and request.files["foto"].filename != "":
            nueva_foto = request.files["foto"]
            nombre_archivo = secure_filename(nueva_foto.filename)
            nueva_foto.save(os.path.join(app.config["UPLOAD_FOLDER"], nombre_archivo))
            reporte.foto_animal = nombre_archivo

        # Vuelve a revisión por admin
        reporte.estado_animal = "pendiente"
        reporte.aprobado = False

        db.session.commit()
        return redirect(url_for("mis_reportes"))

    return render_template("editar_reporte.html", reporte=reporte)

# Páginas informativas
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

# Ejecutar aplicación en modo debug
if __name__ == "__main__":
    app.run(debug=True)

