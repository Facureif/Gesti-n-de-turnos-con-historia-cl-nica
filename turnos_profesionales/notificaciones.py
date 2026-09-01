# turnos_profesionales/notificaciones.py
import threading
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.utils.html import strip_tags

def enviar_correo(destinatario, asunto, mensaje_texto, mensaje_html=None):
    """
    Envía un correo electrónico de forma asíncrona.
    Si mensaje_html es None, solo envía texto plano.
    """
    def _send():
        try:
            if mensaje_html:
                msg = EmailMultiAlternatives(
                    asunto,
                    mensaje_texto,
                    settings.DEFAULT_FROM_EMAIL,
                    [destinatario]
                )
                msg.attach_alternative(mensaje_html, "text/html")
                msg.send(fail_silently=True)
            else:
                send_mail(
                    asunto,
                    mensaje_texto,
                    settings.DEFAULT_FROM_EMAIL,
                    [destinatario],
                    fail_silently=True
                )
        except Exception as e:
            print(f"Error enviando correo a {destinatario}: {e}")

    thread = threading.Thread(target=_send)
    thread.start()


def _datos_basicos_turno(turno):
    """Devuelve un diccionario con los datos más usados en las plantillas."""
    return {
        'paciente': turno.paciente.nombre_completo,
        'fecha': turno.fecha.strftime('%d/%m/%Y'),
        'hora': turno.hora_inicio.strftime('%H:%M'),
        'profesional': turno.profesional.nombre_completo,
        'consultorio': turno.establecimiento.nombre if turno.establecimiento else '—',
        'tipo': turno.tipo_consulta or '—',
    }


def _base_html(titulo, contenido):
    """Genera una plantilla HTML base con estilos simples."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f4f7f6;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                overflow: hidden;
            }}
            .header {{
                background-color: #2c3e50;
                color: white;
                padding: 20px;
                text-align: center;
                font-size: 20px;
                font-weight: bold;
            }}
            .content {{
                padding: 30px;
                color: #333333;
                font-size: 16px;
                line-height: 1.6;
            }}
            .footer {{
                background-color: #ecf0f1;
                padding: 15px;
                text-align: center;
                font-size: 12px;
                color: #7f8c8d;
            }}
            .info-box {{
                background-color: #f8f9fa;
                border-left: 4px solid #3498db;
                padding: 15px;
                margin: 15px 0;
                border-radius: 5px;
            }}
            .btn {{
                display: inline-block;
                background-color: #3498db;
                color: white;
                padding: 10px 20px;
                text-decoration: none;
                border-radius: 5px;
                margin-top: 15px;
            }}
            .emoji {{
                font-size: 24px;
                margin-right: 5px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                {titulo}
            </div>
            <div class="content">
                {contenido}
            </div>
            <div class="footer">
                Este es un correo automático, por favor no respondas a este mensaje.
            </div>
        </div>
    </body>
    </html>
    """


# ---------------------- FUNCIONES DE NOTIFICACIÓN ----------------------

def notificar_creacion_cuenta(paciente, username, password):
    """Envía credenciales al paciente recién creado."""
    if not paciente.email:
        return
    asunto = "🎉 ¡Tu cuenta fue creada exitosamente!"
    texto = f"""
Hola {paciente.nombre_completo},

Tu cuenta en el sistema de turnos fue creada correctamente.

🔑 Usuario: {username}
🔒 Contraseña: {password}

Podés ingresar desde: {settings.URL_LOGIN}

Te recomendamos cambiar tu contraseña después del primer inicio de sesión.

¡Gracias por confiar en nosotros!
"""
    contenido_html = f"""
        <p>Hola <strong>{paciente.nombre_completo}</strong>,</p>
        <p>Tu cuenta en el sistema de turnos fue creada correctamente.</p>
        <div class="info-box">
            <p><span class="emoji">🔑</span> Usuario: <strong>{username}</strong></p>
            <p><span class="emoji">🔒</span> Contraseña: <strong>{password}</strong></p>
        </div>
        <p>Podés ingresar desde: <a href="{settings.URL_LOGIN}" class="btn">Iniciar sesión</a></p>
        <p>Te recomendamos cambiar tu contraseña después del primer inicio de sesión.</p>
        <p>¡Gracias por confiar en nosotros!</p>
    """
    html = _base_html("🎉 ¡Tu cuenta fue creada exitosamente!", contenido_html)
    enviar_correo(paciente.email, asunto, texto, html)


def notificar_turno_asignado(turno, es_nuevo_paciente=False, credenciales=None):
    """Notifica al paciente que se le asignó un turno."""
    if not turno.paciente.email:
        return
    d = _datos_basicos_turno(turno)
    asunto = f"✅ Turno confirmado - {d['profesional']}"
    texto = f"""
Hola {d['paciente']},

Tu turno fue agendado correctamente:

📅 Fecha: {d['fecha']}
⏰ Hora: {d['hora']} hs
🏥 Consultorio: {d['consultorio']}
👨‍⚕️ Profesional: {d['profesional']}
📋 Tipo: {d['tipo']}

"""
    if es_nuevo_paciente and credenciales:
        texto += f"""
🔑 Usuario: {credenciales[0]}
🔒 Contraseña: {credenciales[1]}

"""
    texto += f"""
Podés gestionar tus turnos desde tu panel:
{settings.URL_PANEL_PACIENTE}

¡Gracias por confiar en nosotros!
"""
    contenido_html = f"""
        <p>Hola <strong>{d['paciente']}</strong>,</p>
        <p>Tu turno fue agendado correctamente:</p>
        <div class="info-box">
            <p>📅 Fecha: <strong>{d['fecha']}</strong></p>
            <p>⏰ Hora: <strong>{d['hora']} hs</strong></p>
            <p>🏥 Consultorio: <strong>{d['consultorio']}</strong></p>
            <p>👨‍⚕️ Profesional: <strong>{d['profesional']}</strong></p>
            <p>📋 Tipo: <strong>{d['tipo']}</strong></p>
        </div>
    """
    if es_nuevo_paciente and credenciales:
        contenido_html += f"""
        <div class="info-box">
            <p>🔑 Usuario: <strong>{credenciales[0]}</strong></p>
            <p>🔒 Contraseña: <strong>{credenciales[1]}</strong></p>
        </div>
        """
    contenido_html += f"""
        <p>Podés gestionar tus turnos desde tu panel:</p>
        <p><a href="{settings.URL_PANEL_PACIENTE}" class="btn">Ir al panel</a></p>
        <p>¡Gracias por confiar en nosotros!</p>
    """
    html = _base_html(f"✅ Turno confirmado - {d['profesional']}", contenido_html)
    enviar_correo(turno.paciente.email, asunto, texto, html)


def notificar_turno_confirmado_por_paciente(turno):
    """Notifica al profesional que el paciente confirmó el turno."""
    if not turno.profesional.email:
        return
    d = _datos_basicos_turno(turno)
    asunto = f"🟢 Turno confirmado por paciente: {d['paciente']}"
    texto = f"""
Hola {d['profesional']},

El paciente {d['paciente']} ha confirmado su turno.

📅 Fecha: {d['fecha']}
⏰ Hora: {d['hora']} hs
🏥 Consultorio: {d['consultorio']}

Saludos.
"""
    contenido_html = f"""
        <p>Hola <strong>{d['profesional']}</strong>,</p>
        <p>El paciente <strong>{d['paciente']}</strong> ha confirmado su turno.</p>
        <div class="info-box">
            <p>📅 Fecha: <strong>{d['fecha']}</strong></p>
            <p>⏰ Hora: <strong>{d['hora']} hs</strong></p>
            <p>🏥 Consultorio: <strong>{d['consultorio']}</strong></p>
        </div>
        <p>Saludos.</p>
    """
    html = _base_html("🟢 Turno confirmado por paciente", contenido_html)
    enviar_correo(turno.profesional.email, asunto, texto, html)


def notificar_cancelacion_turno(turno, cancelado_por, motivo=None):
    """
    Notifica la cancelación de un turno.
    cancelado_por: 'profesional', 'paciente', 'sistema'
    """
    d = _datos_basicos_turno(turno)
    # Notificar al paciente
    if turno.paciente.email:
        asunto = "❌ Turno cancelado"
        texto = f"""
Hola {d['paciente']},

Lamentamos informarte que tu turno fue cancelado.

📅 Fecha: {d['fecha']}
⏰ Hora: {d['hora']} hs
👨‍⚕️ Profesional: {d['profesional']}
🏥 Consultorio: {d['consultorio']}
"""
        if motivo:
            texto += f"\nMotivo: {motivo}\n"
        texto += f"""
Podés reprogramar un nuevo turno desde tu panel:
{settings.URL_PANEL_PACIENTE}

Saludos.
"""
        contenido_html = f"""
            <p>Hola <strong>{d['paciente']}</strong>,</p>
            <p>Lamentamos informarte que tu turno fue cancelado.</p>
            <div class="info-box">
                <p>📅 Fecha: <strong>{d['fecha']}</strong></p>
                <p>⏰ Hora: <strong>{d['hora']} hs</strong></p>
                <p>👨‍⚕️ Profesional: <strong>{d['profesional']}</strong></p>
                <p>🏥 Consultorio: <strong>{d['consultorio']}</strong></p>
        """
        if motivo:
            contenido_html += f"<p>Motivo: <strong>{motivo}</strong></p>"
        contenido_html += f"""
            </div>
            <p>Podés reprogramar un nuevo turno desde tu panel:</p>
            <p><a href="{settings.URL_PANEL_PACIENTE}" class="btn">Reprogramar</a></p>
            <p>Saludos.</p>
        """
        html = _base_html("❌ Turno cancelado", contenido_html)
        enviar_correo(turno.paciente.email, asunto, texto, html)

    # Notificar al profesional (si la cancelación no fue hecha por él)
    if turno.profesional.email and cancelado_por != 'profesional':
        asunto = f"🔴 Turno cancelado por {cancelado_por}: {d['paciente']}"
        texto = f"""
Hola {d['profesional']},

El turno de {d['paciente']} fue cancelado ({cancelado_por}).

📅 Fecha: {d['fecha']}
⏰ Hora: {d['hora']} hs

Saludos.
"""
        contenido_html = f"""
            <p>Hola <strong>{d['profesional']}</strong>,</p>
            <p>El turno de <strong>{d['paciente']}</strong> fue cancelado ({cancelado_por}).</p>
            <div class="info-box">
                <p>📅 Fecha: <strong>{d['fecha']}</strong></p>
                <p>⏰ Hora: <strong>{d['hora']} hs</strong></p>
            </div>
            <p>Saludos.</p>
        """
        html = _base_html("🔴 Turno cancelado", contenido_html)
        enviar_correo(turno.profesional.email, asunto, texto, html)


def notificar_reprogramacion_turno(turno_original, turno_nuevo):
    """Notifica al paciente y profesional sobre la reprogramación."""
    d_old = _datos_basicos_turno(turno_original)
    d_new = _datos_basicos_turno(turno_nuevo)
    # Paciente
    if turno_nuevo.paciente.email:
        asunto = "🔄 Turno reprogramado"
        texto = f"""
Hola {d_new['paciente']},

Tu turno fue reprogramado.

❌ Anterior: {d_old['fecha']} a las {d_old['hora']} hs
✅ Nuevo: {d_new['fecha']} a las {d_new['hora']} hs

👨‍⚕️ Profesional: {d_new['profesional']}
🏥 Consultorio: {d_new['consultorio']}

Saludos.
"""
        contenido_html = f"""
            <p>Hola <strong>{d_new['paciente']}</strong>,</p>
            <p>Tu turno fue reprogramado.</p>
            <div class="info-box">
                <p>❌ Anterior: <strong>{d_old['fecha']} a las {d_old['hora']} hs</strong></p>
                <p>✅ Nuevo: <strong>{d_new['fecha']} a las {d_new['hora']} hs</strong></p>
                <p>👨‍⚕️ Profesional: <strong>{d_new['profesional']}</strong></p>
                <p>🏥 Consultorio: <strong>{d_new['consultorio']}</strong></p>
            </div>
            <p>Saludos.</p>
        """
        html = _base_html("🔄 Turno reprogramado", contenido_html)
        enviar_correo(turno_nuevo.paciente.email, asunto, texto, html)
    # Profesional
    if turno_nuevo.profesional.email:
        asunto = f"🔄 Turno reprogramado: {d_new['paciente']}"
        texto = f"""
Hola {d_new['profesional']},

El turno de {d_new['paciente']} fue reprogramado.

❌ Anterior: {d_old['fecha']} a las {d_old['hora']} hs
✅ Nuevo: {d_new['fecha']} a las {d_new['hora']} hs

Saludos.
"""
        contenido_html = f"""
            <p>Hola <strong>{d_new['profesional']}</strong>,</p>
            <p>El turno de <strong>{d_new['paciente']}</strong> fue reprogramado.</p>
            <div class="info-box">
                <p>❌ Anterior: <strong>{d_old['fecha']} a las {d_old['hora']} hs</strong></p>
                <p>✅ Nuevo: <strong>{d_new['fecha']} a las {d_new['hora']} hs</strong></p>
            </div>
            <p>Saludos.</p>
        """
        html = _base_html("🔄 Turno reprogramado", contenido_html)
        enviar_correo(turno_nuevo.profesional.email, asunto, texto, html)


def notificar_recordatorio(turno, horas_antes):
    """Recordatorio al paciente. horas_antes: 24 o 1."""
    if not turno.paciente.email:
        return
    d = _datos_basicos_turno(turno)
    if horas_antes == 24:
        asunto = f"⏰ Recordatorio: tenés un turno mañana"
        texto = f"""
Hola {d['paciente']},

Te recordamos que mañana tenés un turno:

📅 Fecha: {d['fecha']}
⏰ Hora: {d['hora']} hs
🏥 Consultorio: {d['consultorio']}
👨‍⚕️ Profesional: {d['profesional']}

Si no podés asistir, por favor cancelalo desde tu panel.
{settings.URL_PANEL_PACIENTE}

¡Te esperamos!
"""
        contenido_html = f"""
            <p>Hola <strong>{d['paciente']}</strong>,</p>
            <p>Te recordamos que mañana tenés un turno:</p>
            <div class="info-box">
                <p>📅 Fecha: <strong>{d['fecha']}</strong></p>
                <p>⏰ Hora: <strong>{d['hora']} hs</strong></p>
                <p>🏥 Consultorio: <strong>{d['consultorio']}</strong></p>
                <p>👨‍⚕️ Profesional: <strong>{d['profesional']}</strong></p>
            </div>
            <p>Si no podés asistir, por favor cancelalo desde tu panel.</p>
            <p><a href="{settings.URL_PANEL_PACIENTE}" class="btn">Cancelar turno</a></p>
            <p>¡Te esperamos!</p>
        """
        html = _base_html("⏰ Recordatorio de turno", contenido_html)
    elif horas_antes == 1:
        asunto = f"🚨 Tu turno es en 1 hora"
        texto = f"""
Hola {d['paciente']},

Tu turno está por comenzar:

📅 Fecha: {d['fecha']}
⏰ Hora: {d['hora']} hs
🏥 Consultorio: {d['consultorio']}
👨‍⚕️ Profesional: {d['profesional']}

Por favor, llegá unos minutos antes.

¡Te esperamos!
"""
        contenido_html = f"""
            <p>Hola <strong>{d['paciente']}</strong>,</p>
            <p>Tu turno está por comenzar:</p>
            <div class="info-box">
                <p>📅 Fecha: <strong>{d['fecha']}</strong></p>
                <p>⏰ Hora: <strong>{d['hora']} hs</strong></p>
                <p>🏥 Consultorio: <strong>{d['consultorio']}</strong></p>
                <p>👨‍⚕️ Profesional: <strong>{d['profesional']}</strong></p>
            </div>
            <p>Por favor, llegá unos minutos antes.</p>
            <p>¡Te esperamos!</p>
        """
        html = _base_html("🚨 Tu turno es en 1 hora", contenido_html)
    else:
        return
    enviar_correo(turno.paciente.email, asunto, texto, html)


def notificar_turno_completado(turno):
    """Notifica al paciente que su turno fue completado."""
    if not turno.paciente.email:
        return
    d = _datos_basicos_turno(turno)
    asunto = "📋 Turno completado"
    texto = f"""
Hola {d['paciente']},

Tu turno del {d['fecha']} a las {d['hora']} hs fue registrado como completado.

👨‍⚕️ Profesional: {d['profesional']}
🏥 Consultorio: {d['consultorio']}

Gracias por tu visita.
"""
    contenido_html = f"""
        <p>Hola <strong>{d['paciente']}</strong>,</p>
        <p>Tu turno del {d['fecha']} a las {d['hora']} hs fue registrado como completado.</p>
        <div class="info-box">
            <p>👨‍⚕️ Profesional: <strong>{d['profesional']}</strong></p>
            <p>🏥 Consultorio: <strong>{d['consultorio']}</strong></p>
        </div>
        <p>Gracias por tu visita.</p>
    """
    html = _base_html("📋 Turno completado", contenido_html)
    enviar_correo(turno.paciente.email, asunto, texto, html)


def notificar_no_asistio(turno):
    """Notifica al paciente que se registró su inasistencia."""
    if not turno.paciente.email:
        return
    d = _datos_basicos_turno(turno)
    asunto = "⚠️ Registramos tu inasistencia"
    texto = f"""
Hola {d['paciente']},

Lamentamos que no hayas podido asistir a tu turno.

📅 Fecha: {d['fecha']}
⏰ Hora: {d['hora']} hs
👨‍⚕️ Profesional: {d['profesional']}

Si necesitás reprogramar, podés hacerlo desde tu panel:
{settings.URL_PANEL_PACIENTE}

Saludos.
"""
    contenido_html = f"""
        <p>Hola <strong>{d['paciente']}</strong>,</p>
        <p>Lamentamos que no hayas podido asistir a tu turno.</p>
        <div class="info-box">
            <p>📅 Fecha: <strong>{d['fecha']}</strong></p>
            <p>⏰ Hora: <strong>{d['hora']} hs</strong></p>
            <p>👨‍⚕️ Profesional: <strong>{d['profesional']}</strong></p>
        </div>
        <p>Si necesitás reprogramar, podés hacerlo desde tu panel:</p>
        <p><a href="{settings.URL_PANEL_PACIENTE}" class="btn">Reprogramar</a></p>
        <p>Saludos.</p>
    """
    html = _base_html("⚠️ Registramos tu inasistencia", contenido_html)
    enviar_correo(turno.paciente.email, asunto, texto, html)


def notificar_sesiones_bajas(os_paciente, restantes):
    """
    Notifica al paciente y al profesional cuando quedan pocas sesiones (ej. 1).
    os_paciente: instancia de PacienteObraSocial
    restantes: número de sesiones restantes
    """
    if restantes != 1:
        return  # Solo avisamos cuando queda exactamente 1

    paciente = os_paciente.paciente
    profesional = os_paciente.profesional
    obra_social = os_paciente.obra_social

    if not paciente.email:
        return

    asunto = f"⚠️ Última sesión disponible con {obra_social.nombre}"
    texto = f"""
Hola {paciente.nombre_completo},

Te informamos que te queda **1 sesión** disponible con la obra social {obra_social.nombre}.

👨‍⚕️ Profesional: {profesional.nombre_completo}
📋 Plan: {os_paciente.plan.nombre if os_paciente.plan else 'Sin plan'}

Es importante que consultes con tu obra social para renovar la autorización de sesiones si lo necesitás.

Podés ver tus sesiones desde tu panel:
{settings.URL_PANEL_PACIENTE}

Saludos.
"""
    contenido_html = f"""
        <p>Hola <strong>{paciente.nombre_completo}</strong>,</p>
        <p>Te informamos que te queda <strong>1 sesión</strong> disponible con la obra social <strong>{obra_social.nombre}</strong>.</p>
        <div class="info-box">
            <p>👨‍⚕️ Profesional: <strong>{profesional.nombre_completo}</strong></p>
            <p>📋 Plan: <strong>{os_paciente.plan.nombre if os_paciente.plan else 'Sin plan'}</strong></p>
        </div>
        <p>Es importante que consultes con tu obra social para renovar la autorización de sesiones si lo necesitás.</p>
        <p>Podés ver tus sesiones desde tu panel:</p>
        <p><a href="{settings.URL_PANEL_PACIENTE}" class="btn">Ver sesiones</a></p>
        <p>Saludos.</p>
    """
    html = _base_html(f"⚠️ Última sesión disponible con {obra_social.nombre}", contenido_html)
    enviar_correo(paciente.email, asunto, texto, html)

    # Notificar al profesional (si tiene email)
    if profesional.email:
        asunto_prof = f"⚠️ Paciente {paciente.nombre_completo} se queda sin sesiones"
        texto_prof = f"""
Hola {profesional.nombre_completo},

El paciente {paciente.nombre_completo} tiene solo 1 sesión restante con {obra_social.nombre}.

📋 Plan: {os_paciente.plan.nombre if os_paciente.plan else 'Sin plan'}

Saludos.
"""
        contenido_html_prof = f"""
            <p>Hola <strong>{profesional.nombre_completo}</strong>,</p>
            <p>El paciente <strong>{paciente.nombre_completo}</strong> tiene solo <strong>1 sesión</strong> restante con <strong>{obra_social.nombre}</strong>.</p>
            <div class="info-box">
                <p>📋 Plan: <strong>{os_paciente.plan.nombre if os_paciente.plan else 'Sin plan'}</strong></p>
            </div>
            <p>Saludos.</p>
        """
        html_prof = _base_html("⚠️ Paciente se queda sin sesiones", contenido_html_prof)
        enviar_correo(profesional.email, asunto_prof, texto_prof, html_prof)


def notificar_sesiones_agotadas(os_paciente):
    """
    Notifica al paciente y al profesional cuando las sesiones llegan a 0.
    """
    paciente = os_paciente.paciente
    profesional = os_paciente.profesional
    obra_social = os_paciente.obra_social

    if not paciente.email:
        return

    asunto = f"❌ Sin sesiones disponibles con {obra_social.nombre}"
    texto = f"""
Hola {paciente.nombre_completo},

Te informamos que ya no tenés sesiones disponibles con la obra social {obra_social.nombre}.

👨‍⚕️ Profesional: {profesional.nombre_completo}
📋 Plan: {os_paciente.plan.nombre if os_paciente.plan else 'Sin plan'}

Para continuar con la atención, por favor renová la autorización de sesiones con tu obra social o consultá con el profesional.

Saludos.
"""
    contenido_html = f"""
        <p>Hola <strong>{paciente.nombre_completo}</strong>,</p>
        <p>Te informamos que ya <strong>no tenés sesiones</strong> disponibles con la obra social <strong>{obra_social.nombre}</strong>.</p>
        <div class="info-box">
            <p>👨‍⚕️ Profesional: <strong>{profesional.nombre_completo}</strong></p>
            <p>📋 Plan: <strong>{os_paciente.plan.nombre if os_paciente.plan else 'Sin plan'}</strong></p>
        </div>
        <p>Para continuar con la atención, por favor renová la autorización de sesiones con tu obra social o consultá con el profesional.</p>
        <p>Saludos.</p>
    """
    html = _base_html(f"❌ Sin sesiones disponibles con {obra_social.nombre}", contenido_html)
    enviar_correo(paciente.email, asunto, texto, html)

    # Notificar al profesional
    if profesional.email:
        asunto_prof = f"❌ Paciente {paciente.nombre_completo} sin sesiones"
        texto_prof = f"""
Hola {profesional.nombre_completo},

El paciente {paciente.nombre_completo} se quedó sin sesiones con {obra_social.nombre}.

📋 Plan: {os_paciente.plan.nombre if os_paciente.plan else 'Sin plan'}

Saludos.
"""
        contenido_html_prof = f"""
            <p>Hola <strong>{profesional.nombre_completo}</strong>,</p>
            <p>El paciente <strong>{paciente.nombre_completo}</strong> se quedó <strong>sin sesiones</strong> con <strong>{obra_social.nombre}</strong>.</p>
            <div class="info-box">
                <p>📋 Plan: <strong>{os_paciente.plan.nombre if os_paciente.plan else 'Sin plan'}</strong></p>
            </div>
            <p>Saludos.</p>
        """
        html_prof = _base_html("❌ Paciente sin sesiones", contenido_html_prof)
        enviar_correo(profesional.email, asunto_prof, texto_prof, html_prof)    