from datetime import datetime
import os
import shutil
import sqlite3
import sys
import webbrowser
import threading
from flask import Flask, redirect, render_template, request, session, url_for

# --- CONFIGURACIÓN DE RUTAS ABSOLUTAS Y RENDER ---
base_dir = os.path.dirname(os.path.abspath(__file__))

if os.path.exists('/var/data'):
    db_base_dir = '/var/data'
else:
    db_base_dir = base_dir

template_dir = os.path.join(base_dir, 'templates')
static_dir = os.path.join(base_dir, 'static')

app = Flask(
    __name__, template_folder=template_dir, static_folder=static_dir
)
app.secret_key = 'sanitas_secreto_key_2026'

DB_PATH = os.path.join(db_base_dir, 'policlinica.db')


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('PRAGMA journal_mode=WAL;')
    except Exception:
        pass
    return conn


def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                rol TEXT
            )
        ''')

        usuarios_default = [
            ('doctora', 'sanitas123', 'doctora'),
            ('secretaria', 'sanitas123', 'secretaria'),
            ('ginecologia', 'sanitas123', 'medico'),
            ('cardiologia', 'sanitas123', 'medico'),
            ('pediatria', 'sanitas123', 'medico'),
            ('clinica', 'sanitas123', 'medico'),
            ('psicologia', 'sanitas123', 'medico'),
            ('traumatologia', 'sanitas123', 'medico'),
            ('nutricion', 'sanitas123', 'medico'),
            ('otros', 'sanitas123', 'medico'),
        ]

        for user, pwd, rol in usuarios_default:
            cursor.execute(
                'INSERT OR IGNORE INTO usuarios (username, password, rol) VALUES (?, ?, ?)',
                (user, pwd, rol),
            )

        cursor.execute(
            "UPDATE usuarios SET password = 'sanitas123' WHERE LOWER(username) = 'secretaria'"
        )

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pacientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT,
                cedula TEXT,
                telefono TEXT,
                edad TEXT,
                fecha_nacimiento TEXT
            )
        ''')

        cursor.execute("PRAGMA table_info(pacientes)")
        cols_pacientes = [col[1] for col in cursor.fetchall()]
        if 'edad' not in cols_pacientes:
            try:
                cursor.execute("ALTER TABLE pacientes ADD COLUMN edad TEXT")
            except:
                pass

        tablas_esp = [
            'f_ginecologia', 'f_clinica', 'f_psicologia', 'f_traumatologia',
            'f_nutricion', 'f_pediatria', 'f_cardiologia', 'f_otros'
        ]
        
        for t in tablas_esp:
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {t} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    paciente_id INTEGER, 
                    fecha_consulta TEXT, 
                    hora_turno TEXT, 
                    estado TEXT DEFAULT 'Agendado', 
                    motivo TEXT, 
                    procedencia TEXT, 
                    medio_llegada TEXT,
                    diagnostico TEXT, 
                    receta TEXT, 
                    indicaciones TEXT, 
                    laboratorio TEXT, 
                    estudios TEXT, 
                    fecha_registro TEXT
                )
            ''')
        conn.commit()


# --- RUTAS DE LA APLICACIÓN ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with get_db_connection() as conn:
            user = conn.execute(
                'SELECT * FROM usuarios WHERE username = ? AND password = ?',
                (username, password),
            ).fetchone()
            if user:
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['rol'] = user['rol']
                return redirect(url_for('index'))
            else:
                error = 'Usuario o contraseña incorrectos.'
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/cambiar_password', methods=['GET', 'POST'])
def cambiar_password():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    mensaje = None
    error = None
    if request.method == 'POST':
        password_actual = request.form.get('password_actual')
        nueva_password = request.form.get('nueva_password')
        user_id = session.get('user_id')
        with get_db_connection() as conn:
            user = conn.execute(
                'SELECT * FROM usuarios WHERE id = ? AND password = ?',
                (user_id, password_actual),
            ).fetchone()
            if user:
                conn.execute(
                    'UPDATE usuarios SET password = ? WHERE id = ?',
                    (nueva_password, user_id),
                )
                conn.commit()
                mensaje = '¡Contraseña actualizada con éxito!'
            else:
                error = 'La contraseña actual es incorrecta.'
    return render_template(
        'cambiar_password.html',
        mensaje=mensaje,
        error=error,
        rol=session.get('rol'),
        username=session.get('username'),
    )


@app.route('/cambiar_estado/<tabla>/<int:id_registro>/<nuevo_estado>')
def cambiar_estado(tabla, id_registro, nuevo_estado):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    tablas_validas = [
        'f_ginecologia', 'f_clinica', 'f_psicologia', 'f_traumatologia',
        'f_nutricion', 'f_pediatria', 'f_cardiologia', 'f_otros'
    ]
    if tabla in tablas_validas:
        with get_db_connection() as conn:
            conn.execute(f'UPDATE {tabla} SET estado = ? WHERE id = ?', (nuevo_estado, id_registro))
            conn.commit()
    endpoint_map = {
        'f_ginecologia': 'ginecologia', 'f_clinica': 'clinica_medica',
        'f_psicologia': 'psicologia', 'f_traumatologia': 'traumatologia',
        'f_nutricion': 'nutricion', 'f_pediatria': 'pediatria',
        'f_cardiologia': 'cardiologia', 'f_otros': 'otros',
    }
    return redirect(url_for(endpoint_map.get(tabla, 'index')))


@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template(
        'index.html', rol=session.get('rol'), username=session.get('username')
    )


@app.route('/hacer_backup')
def hacer_backup():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    backup_dir = os.path.join(base_dir, 'backups')
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    fecha_str = datetime.now().strftime('%Y-%m-%d_%H-%M')
    backup_filename = os.path.join(backup_dir, f'policlinica_respaldo_{fecha_str}.db')
    try:
        shutil.copy(DB_PATH, backup_filename)
        mensaje = "✅ ¡Copia de seguridad creada con éxito!"
    except Exception as e:
        mensaje = '❌ Error al crear la copia de seguridad.'
    return render_template(
        'index.html', rol=session.get('rol'), username=session.get('username'), mensaje_backup=mensaje
    )


@app.route('/pacientes')
def listar_pacientes():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    busqueda = request.args.get('q', '').strip()
    with get_db_connection() as conn:
        if busqueda:
            query = "SELECT * FROM pacientes WHERE cedula LIKE ? OR nombre LIKE ? GROUP BY cedula ORDER BY id DESC"
            pacientes = conn.execute(query, (f'%{busqueda}%', f'%{busqueda}%')).fetchall()
        else:
            pacientes = conn.execute('SELECT * FROM pacientes GROUP BY cedula ORDER BY id DESC').fetchall()
    return render_template(
        'lista_pacientes.html', pacientes=pacientes, rol=session.get('rol'), username=session.get('username'), busqueda=busqueda
    )


@app.route('/historial_paciente/<int:paciente_id>')
def historial_paciente(paciente_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # RESTRICCIÓN: La secretaría no puede ver historiales médicos ni recetas
    if session.get('rol') == 'secretaria':
        return redirect(url_for('index'))
    
    with get_db_connection() as conn:
        paciente = conn.execute('SELECT * FROM pacientes WHERE id = ?', (paciente_id,)).fetchone()
        if not paciente:
            return redirect(url_for('listar_pacientes'))
        cedula = paciente['cedula']
        if cedula:
            mismos_pacientes = conn.execute('SELECT id FROM pacientes WHERE cedula = ?', (cedula,)).fetchall()
            paciente_ids = [row['id'] for row in mismos_pacientes]
        else:
            paciente_ids = [paciente_id]
        placeholders = ','.join(['?'] * len(paciente_ids))
        historial = []
        tablas = [
            ('Ginecología y Obstetricia', 'f_ginecologia'), ('Clínica Médica', 'f_clinica'),
            ('Pediatría', 'f_pediatria'), ('Cardiología', 'f_cardiologia'),
            ('Psicología Clínica', 'f_psicologia'), ('Traumatología', 'f_traumatologia'),
            ('Nutrición', 'f_nutricion'), ('Otros Servicios', 'f_otros'),
        ]
        for nombre_esp, tabla in tablas:
            query = f'SELECT *, ? as especialidad, ? as nombre_tabla FROM {tabla} WHERE paciente_id IN ({placeholders})'
            params = [nombre_esp, tabla] + paciente_ids
            registros = conn.execute(query, params).fetchall()
            historial.extend(registros)
        historial = sorted(historial, key=lambda x: x['fecha_consulta'] if x['fecha_consulta'] else '', reverse=True)
    return render_template(
        'historial_compartido.html', paciente=paciente, historial=historial, rol=session.get('rol'), username=session.get('username')
    )


@app.route('/editar_registro/<tabla>/<int:registro_id>', methods=['GET', 'POST'])
def editar_registro(tabla, registro_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    with get_db_connection() as conn:
        registro = conn.execute(f'SELECT * FROM {tabla} WHERE id = ?', (registro_id,)).fetchone()
        if not registro:
            return redirect(url_for('index'))
        paciente = conn.execute('SELECT * FROM pacientes WHERE id = ?', (registro['paciente_id'],)).fetchone()
        
        if request.method == 'POST':
            cursor = conn.cursor()
            
            nuevo_nombre = request.form.get('nombre_paciente')
            nueva_cedula = request.form.get('cedula_paciente')
            nuevo_telefono = request.form.get('telefono_paciente')
            nueva_edad = request.form.get('edad_paciente')
            nuevo_motivo = request.form.get('motivo')
            
            if nuevo_nombre:
                cursor.execute('UPDATE pacientes SET nombre = ?, cedula = ?, telefono = ?, edad = ? WHERE id = ?',
                               (nuevo_nombre, nueva_cedula, nuevo_telefono, nueva_edad, registro['paciente_id']))
            if nuevo_motivo:
                cursor.execute(f'UPDATE {tabla} SET motivo = ? WHERE id = ?', (nuevo_motivo, registro_id))
            
            conn.commit()
            return redirect(url_for('listar_pacientes'))
            
    return render_template('editar_registro.html', registro=registro, paciente=paciente, tabla=tabla, rol=session.get('rol'))


@app.route('/eliminar_registro/<tabla>/<int:registro_id>', methods=['GET', 'POST'])
def eliminar_registro(tabla, registro_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    with get_db_connection() as conn:
        registro = conn.execute(f'SELECT * FROM {tabla} WHERE id = ?', (registro_id,)).fetchone()
        if registro:
            paciente_id = registro['paciente_id']
            conn.execute(f'DELETE FROM {tabla} WHERE id = ?', (registro_id,))
            conn.commit()
    return redirect(url_for('listar_pacientes'))


@app.route('/eliminar_paciente/<int:paciente_id>', methods=['GET', 'POST'])
def eliminar_paciente(paciente_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    with get_db_connection() as conn:
        paciente = conn.execute('SELECT cedula FROM pacientes WHERE id = ?', (paciente_id,)).fetchone()
        if paciente:
            cedula = paciente['cedula']
            mismos = conn.execute('SELECT id FROM pacientes WHERE cedula = ?', (cedula,)).fetchall()
            p_ids = [row['id'] for row in mismos]
            tablas = [
                'f_ginecologia', 'f_clinica', 'f_psicologia', 'f_traumatologia',
                'f_nutricion', 'f_pediatria', 'f_cardiologia', 'f_otros'
            ]
            for t in tablas:
                for pid in p_ids:
                    conn.execute(f'DELETE FROM {t} WHERE paciente_id = ?', (pid,))
            conn.execute('DELETE FROM pacientes WHERE cedula = ?', (cedula,))
            conn.commit()
    return redirect(url_for('listar_pacientes'))


def guardar_registro_comun(request_form, nombre_tabla, especialidad_str, endpoint_retorno):
    paciente_nombre = request_form['paciente_nombre']
    cedula = request_form.get('cedula', '')
    telefono = request_form.get('telefono', '')
    edad = request_form.get('edad', '')
    fecha_nacimiento = request_form.get('fecha_nacimiento', '')
    fecha_consulta = request_form['fecha_consulta']
    hora_turno = request_form.get('hora_turno', '08:00')
    estado = request_form.get('estado', 'Agendado')
    motivo = request_form['motivo']
    procedencia = request_form.get('procedencia', '')
    medio_llegada = request_form.get('medio_llegada', '')
    rol_usuario = session.get('rol')
    is_medico = rol_usuario in ['doctora', 'medico']

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO pacientes (nombre, cedula, telefono, edad, fecha_nacimiento) VALUES (?, ?, ?, ?, ?)',
            (paciente_nombre, cedula, telefono, edad, fecha_nacimiento),
        )
        paciente_id = cursor.lastrowid
        campos_ignorar = [
            'paciente_nombre', 'cedula', 'telefono', 'edad', 'fecha_nacimiento',
            'fecha_consulta', 'hora_turno', 'estado', 'motivo', 'procedencia', 'medio_llegada', 'embarazada'
        ]
        keys = []
        values = []
        for key, val in request_form.items():
            if key not in campos_ignorar:
                keys.append(key)
                values.append(val if is_medico else '')
        keys_sql = ', '.join(['paciente_id', 'fecha_consulta', 'hora_turno', 'estado', 'motivo', 'procedencia', 'medio_llegada'] + keys)
        placeholders_sql = ', '.join(['?'] * (7 + len(keys)))
        vals_sql = [paciente_id, fecha_consulta, hora_turno, estado, motivo, procedencia, medio_llegada] + values
        query = f"INSERT INTO {nombre_tabla} ({keys_sql}, fecha_registro) VALUES ({placeholders_sql}, datetime('now'))"
        cursor.execute(query, vals_sql)
        conn.commit()

    return redirect(url_for(endpoint_retorno))


@app.route('/ver_receta')
def ver_receta():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template(
        'receta.html', paciente=request.args.get('paciente', ''), cedula=request.args.get('cedula', ''),
        telefono=request.args.get('telefono', ''), especialidad=request.args.get('especialidad', ''),
        receta=request.args.get('receta', ''), indicaciones=request.args.get('indicaciones', ''),
        laboratorio=request.args.get('laboratorio', ''), estudios=request.args.get('estudios', ''), fecha=request.args.get('fecha', '')
    )


def obtener_agenda_especialidad(nombre_tabla):
    with get_db_connection() as conn:
        registros = conn.execute(
            f"""
            SELECT f.*, p.nombre as paciente_nombre, p.cedula, p.telefono, p.edad, p.fecha_nacimiento, ? as nombre_tabla
            FROM {nombre_tabla} f
            JOIN pacientes p ON f.paciente_id = p.id
            ORDER BY CASE WHEN f.hora_turno = 'En el momento' THEN '23:59' ELSE f.hora_turno END ASC, f.id DESC LIMIT 30
            """, (nombre_tabla,)
        ).fetchall()
    return registros


@app.route('/ginecologia', methods=['GET', 'POST'])
def ginecologia():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST': return guardar_registro_comun(request.form, 'f_ginecologia', 'Ginecología y Obstetricia', 'ginecologia')
    return render_template('ginecologia.html', rol=session.get('rol'), registros=obtener_agenda_especialidad('f_ginecologia'))


@app.route('/clinica_medica', methods=['GET', 'POST'])
def clinica_medica():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST': return guardar_registro_comun(request.form, 'f_clinica', 'Clínica Médica', 'clinica_medica')
    return render_template('clinica_medica.html', rol=session.get('rol'), registros=obtener_agenda_especialidad('f_clinica'))


@app.route('/psicologia', methods=['GET', 'POST'])
def psicologia():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST': return guardar_registro_comun(request.form, 'f_psicologia', 'Psicología Clínica', 'psicologia')
    return render_template('psicologia.html', rol=session.get('rol'), registros=obtener_agenda_especialidad('f_psicologia'))


@app.route('/traumatologia', methods=['GET', 'POST'])
def traumatologia():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST': return guardar_registro_comun(request.form, 'f_traumatologia', 'Traumatología', 'traumatologia')
    return render_template('traumatologia.html', rol=session.get('rol'), registros=obtener_agenda_especialidad('f_traumatologia'))


@app.route('/nutricion', methods=['GET', 'POST'])
def nutricion():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST': return guardar_registro_comun(request.form, 'f_nutricion', 'Nutrición', 'nutricion')
    return render_template('nutricion.html', rol=session.get('rol'), registros=obtener_agenda_especialidad('f_nutricion'))


@app.route('/pediatria', methods=['GET', 'POST'])
def pediatria():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST': return guardar_registro_comun(request.form, 'f_pediatria', 'Pediatría', 'pediatria')
    return render_template('pediatria.html', rol=session.get('rol'), registros=obtener_agenda_especialidad('f_pediatria'))


@app.route('/cardiologia', methods=['GET', 'POST'])
def cardiologia():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST': return guardar_registro_comun(request.form, 'f_cardiologia', 'Cardiología', 'cardiologia')
    return render_template('cardiologia.html', rol=session.get('rol'), registros=obtener_agenda_especialidad('f_cardiologia'))


@app.route('/otros', methods=['GET', 'POST'])
def otros():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST': return guardar_registro_comun(request.form, 'f_otros', 'Otros Servicios', 'otros')
    return render_template('otros.html', rol=session.get('rol'), registros=obtener_agenda_especialidad('f_otros'))


@app.route('/atender_consulta/<tabla>/<int:id_registro>/<int:paciente_id>', methods=['GET', 'POST'])
def atender_consulta(tabla, id_registro, paciente_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    tablas_validas = [
        'f_ginecologia', 'f_clinica', 'f_psicologia', 'f_traumatologia',
        'f_nutricion', 'f_pediatria', 'f_cardiologia', 'f_otros'
    ]
    if tabla not in tablas_validas:
        return redirect(url_for('index'))
    with get_db_connection() as conn:
        conn.execute(f"UPDATE {tabla} SET estado = 'Atendido' WHERE id = ?", (id_registro,))
        conn.commit()
        paciente_row = conn.execute('SELECT * FROM pacientes WHERE id = ?', (paciente_id,)).fetchone()
        paciente = dict(paciente_row) if paciente_row else {}
        registro_row = conn.execute(f'SELECT * FROM {tabla} WHERE id = ?', (id_registro,)).fetchone()
        registro = dict(registro_row) if registro_row else {}
        if request.method == 'POST':
            cursor = conn.cursor()
            cursor.execute(f'PRAGMA table_info({tabla})')
            cols = [col['name'] for col in cursor.fetchall()]
            updates = []
            values = []
            for key, val in request.form.items():
                if key in cols and key not in ['id', 'paciente_id', 'fecha_registro']:
                    updates.append(f'{key} = ?')
                    values.append(val)
            if updates:
                values.append(id_registro)
                query = f"UPDATE {tabla} SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, values)
                conn.commit()
            return redirect(url_for('atender_consulta', tabla=tabla, id_registro=id_registro, paciente_id=paciente_id))
        cedula = paciente.get('cedula')
        if cedula:
            mismos_pacientes = conn.execute('SELECT id FROM pacientes WHERE cedula = ?', (cedula,)).fetchall()
            paciente_ids = [row['id'] for row in mismos_pacientes]
        else:
            paciente_ids = [paciente_id]
        placeholders = ','.join(['?'] * len(paciente_ids))
        query_historial = f'SELECT * FROM {tabla} WHERE paciente_id IN ({placeholders}) AND id != ? ORDER BY fecha_consulta DESC'
        params_historial = paciente_ids + [id_registro]
        regs = conn.execute(query_historial, params_historial).fetchall()
        historial = [dict(row) for row in regs]

    plantillas_especialidades = {
        'f_ginecologia': 'ginecologia.html', 'f_clinica': 'clinica_medica.html',
        'f_pediatria': 'pediatria.html', 'f_cardiologia': 'cardiologia.html',
        'f_psicologia': 'psicologia.html', 'f_traumatologia': 'traumatologia.html',
        'f_nutricion': 'nutricion.html', 'f_otros': 'otros.html',
    }
    plantilla_destino = plantillas_especialidades.get(tabla, 'index.html')
    return render_template(
        plantilla_destino, paciente=paciente, registro=registro, tabla=tabla,
        id_registro=id_registro, historial=historial, rol=session.get('rol'), username=session.get('username')
    )


# --- INICIALIZACIÓN SEGURA PARA PRODUCCIÓN (GUNICORN / RENDER) ---
try:
    init_db()
except Exception as e:
    print(f"Error al inicializar la base de datos: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    threading.Timer(1.0, lambda: webbrowser.open(f'http://127.0.0.1:{port}')).start()
    app.run(host='0.0.0.0', port=port, debug=False)
