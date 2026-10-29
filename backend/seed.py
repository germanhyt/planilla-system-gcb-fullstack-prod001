"""Semilla ficticia y anonimizada (idempotente). Ver README: patrones derivados del Excel de referencia.
NO contiene nombres, DNI ni sueldos reales. Uso: python seed.py"""
import random
from datetime import date, datetime, time, timedelta

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Empresa, HorarioPlan, Marca, RuleSet, Sede, TipoContrato, Trabajador, TurnoPlantilla, Unidad, Usuario
from app.rules import CAVAS, GCB_SA
from app.security import hash_password

rnd = random.Random(2026)
NOMBRES = ["Ana", "Luis", "Rosa", "Jorge", "Carmen", "Pedro", "Lucía", "Miguel", "Elena", "Raúl", "Sofía", "Diego"]
APELLIDOS = ["Ficticio", "Demo", "Prueba", "Ejemplo", "Muestra", "Simulado"]

# Patrones derivados (agregados) del tareo de referencia de Cavas: inicio/fin de turno más frecuentes.
TURNOS_CAVAS = [("Noche 19-02", time(19), time(2), 0), ("Noche 18-02", time(18), time(2), 0),
                ("Tarde-noche 17-00", time(17), time(0), 0), ("Noche 19-03 cierre", time(19), time(3), 45),
                ("Noche 20-03 cierre", time(20), time(3), 0), ("Día 11-18", time(11), time(18), 0),
                ("Día 11:30-18:30", time(11, 30), time(18, 30), 0), ("Tarde 16-22", time(16), time(22), 0),
                ("Partido FT 14-23", time(14), time(23), 45)]
TURNOS_PARKING = [("Rotativo 06-14", time(6), time(14), 45), ("Rotativo 14-22", time(14), time(22), 45),
                  ("Rotativo 22-06", time(22), time(6), 45)]
AREAS_CAVAS = [("Salón", "Mozo/a", 10), ("Bar", "Bartender", 6), ("Cocina", "Cocinero/a", 7), ("Cocina", "Ayudante de cocina", 3),
               ("Caja", "Cajero/a", 2), ("Seguridad", "Anfitrión/Seguridad", 2), ("Administración", "Supervisor/a", 2)]


def get_or_create(db, model, where: dict, **extra):
    obj = db.scalar(select(model).filter_by(**where))
    if not obj:
        obj = model(**where, **extra)
        db.add(obj)
        db.flush()
    return obj


def main():
    db = SessionLocal()
    tc = {c: get_or_create(db, TipoContrato, {"codigo": c}, nombre=n, horas_mes=h, jornada_diaria_min=j, es_part_time=pt,
                           refrigerio_min=45)
          for c, n, h, j, pt in [("FT", "Tiempo completo", 208, 480, False), ("PT85", "Part time 85 h/mes", 85, 240, True),
                                 ("PT102", "Part time 102 h/mes", 102, 240, True)]}
    cav = get_or_create(db, Empresa, {"codigo": "CAVAS"}, razon_social="CAVAS SAC", ruc="20000000001")
    gcb = get_or_create(db, Empresa, {"codigo": "GCBSA"}, razon_social="GCB SA", ruc="20000000002")
    u_cav = get_or_create(db, Unidad, {"empresa_id": cav.id, "codigo": "SISA"}, nombre="Cavas Sisa")
    u_ref = get_or_create(db, Unidad, {"empresa_id": gcb.id, "codigo": "REF"}, nombre="Refugio")
    u_par = get_or_create(db, Unidad, {"empresa_id": gcb.id, "codigo": "PARK"}, nombre="Parking Explanada")
    # Coordenadas ficticias (zona Huaraz), geocerca 80-150 m
    s_cav = get_or_create(db, Sede, {"unidad_id": u_cav.id, "nombre": "Local Sisa"}, lat=-9.527000, lng=-77.528000, radio_geocerca_m=100)
    get_or_create(db, Sede, {"unidad_id": u_ref.id, "nombre": "Refugio Principal"}, lat=-9.530500, lng=-77.531000, radio_geocerca_m=150)
    s_par = get_or_create(db, Sede, {"unidad_id": u_par.id, "nombre": "Explanada"}, lat=-9.525200, lng=-77.526800, radio_geocerca_m=80)
    for u, pats in ((u_cav, TURNOS_CAVAS), (u_par, TURNOS_PARKING)):
        for n, a, b, r in pats:
            get_or_create(db, TurnoPlantilla, {"unidad_id": u.id, "nombre": n}, inicio=a, fin=b, refrigerio_min=r)
    for e, cfg in ((cav, CAVAS), (gcb, GCB_SA)):
        get_or_create(db, RuleSet, {"empresa_id": e.id, "version": 1}, valid_from=date(2026, 1, 1), config=cfg,
                      motivo="Reglas confirmadas Sprint 1")
    pw = hash_password(settings.seed_password)
    users = {}
    for rol, unidad in (("admin", None), ("rrhh", None), ("jefe", u_cav.id), ("trabajador", None)):
        users[rol] = get_or_create(db, Usuario, {"email": f"{rol}@demo.gcb.pe"}, password_hash=pw, rol=rol,
                                   nombre=f"Usuario {rol.upper()} demo", unidad_id=unidad)
    get_or_create(db, Usuario, {"email": "jefe.parking@demo.gcb.pe"}, password_hash=pw, rol="jefe",
                  nombre="Jefe Parking demo", unidad_id=u_par.id)
    # Cavas: 32 personas (mezcla observada ~6 FT / 26 PT); PT repartido PT85/PT102 (supuesto: 50/50)
    contratos = ["FT"] * 6 + ["PT85"] * 13 + ["PT102"] * 13
    puestos = [(a, c) for a, c, n in AREAS_CAVAS for _ in range(n)]
    n = 0
    for i, (ct, (area, cargo)) in enumerate(zip(contratos, puestos, strict=True), 1):
        n += 1
        get_or_create(db, Trabajador, {"codigo": f"CAV-{i:03d}"}, empresa_id=cav.id, unidad_id=u_cav.id, sede_id=s_cav.id,
                      doc_tipo="FICT", doc_numero=f"X{i:07d}", nombres=rnd.choice(NOMBRES), apellidos=rnd.choice(APELLIDOS),
                      area=area, cargo=cargo, tipo_contrato_id=tc[ct].id, fecha_ingreso=date(2025, rnd.randint(1, 12), 1),
                      jefe_usuario_id=users["jefe"].id, usuario_id=users["trabajador"].id if i == 7 else None)
    # Parking (GCB SA): 8 personas, 24/7 rotativo, FT
    for i in range(1, 9):
        n += 1
        get_or_create(db, Trabajador, {"codigo": f"PAR-{i:03d}"}, empresa_id=gcb.id, unidad_id=u_par.id, sede_id=s_par.id,
                      doc_tipo="FICT", doc_numero=f"Y{i:07d}", nombres=rnd.choice(NOMBRES), apellidos=rnd.choice(APELLIDOS),
                      area="Operaciones", cargo="Controlador/a de parking", tipo_contrato_id=tc["FT"].id,
                      fecha_ingreso=date(2025, 6, 1))
    
    # Sprint 3: Agregar horarios semanales de muestra para trabajadores
    trabajadores = db.scalars(select(Trabajador).where(Trabajador.activo).limit(10)).all()
    turnos_cavas_ids = db.scalars(select(TurnoPlantilla.id).where(TurnoPlantilla.unidad_id == u_cav.id)).all()
    turnos_parking_ids = db.scalars(select(TurnoPlantilla.id).where(TurnoPlantilla.unidad_id == u_par.id)).all()
    
    # Semana actual para horarios
    hoy = date.today()
    semana_inicio = hoy - timedelta(days=hoy.weekday())
    
    for trab in trabajadores[:5]:  # primeros 5 de Cavas
        if trab.unidad_id == u_cav.id and turnos_cavas_ids:
            lun_tur = rnd.choice(turnos_cavas_ids)
            mar_tur = rnd.choice(turnos_cavas_ids)
            mie_tur = rnd.choice(turnos_cavas_ids)
            jue_tur = rnd.choice(turnos_cavas_ids)
            vie_tur = rnd.choice(turnos_cavas_ids)
            sab_tur = rnd.choice(turnos_cavas_ids)
            dom_tur = None  # descanso
            
            get_or_create(
                db,
                HorarioPlan,
                {"trabajador_id": trab.id, "semana_inicio": semana_inicio, "version": 1},
                lunes_plantilla_id=lun_tur,
                martes_plantilla_id=mar_tur,
                miercoles_plantilla_id=mie_tur,
                jueves_plantilla_id=jue_tur,
                viernes_plantilla_id=vie_tur,
                sabado_plantilla_id=sab_tur,
                domingo_plantilla_id=dom_tur,
                creado_por=users["admin"].id,
            )
    
    for trab in trabajadores[5:8]:  # algunos de Parking
        if trab.unidad_id == u_par.id and turnos_parking_ids:
            turno = rnd.choice(turnos_parking_ids)
            get_or_create(
                db,
                HorarioPlan,
                {"trabajador_id": trab.id, "semana_inicio": semana_inicio, "version": 1},
                lunes_plantilla_id=turno,
                martes_plantilla_id=turno,
                miercoles_plantilla_id=turno,
                jueves_plantilla_id=turno,
                viernes_plantilla_id=turno,
                sabado_plantilla_id=turno,
                domingo_plantilla_id=None,  # descanso
                creado_por=users["admin"].id,
            )
    
    # Sprint 3: Agregar marcas de muestra para los últimos 5 días
    marcas_creadas = 0
    for dia_offset in range(5):
        dia = hoy - timedelta(days=dia_offset)
        ts_base = datetime.combine(dia, time(8, 0))
        
        for trab in trabajadores[:3]:  # primeros 3 trabajadores
            entrada_ts = ts_base.replace(hour=8, minute=rnd.randint(0, 15))
            salida_ts = ts_base.replace(hour=17, minute=rnd.randint(0, 30))
            
            sede = db.scalar(select(Sede).where(Sede.id == trab.sede_id))
            if sede:
                get_or_create(
                    db,
                    Marca,
                    {"trabajador_id": trab.id, "ts_servidor": entrada_ts},
                    tipo="entrada",
                    lat=float(sede.lat) + rnd.uniform(-0.0001, 0.0001),
                    lng=float(sede.lng) + rnd.uniform(-0.0001, 0.0001),
                    distancia_m=rnd.uniform(5, 30),
                    sede_id=sede.id,
                    metodo="gps",
                    validacion_estado="ok",
                    sincronizado_offline=False,
                )
                marcas_creadas += 1
                
                get_or_create(
                    db,
                    Marca,
                    {"trabajador_id": trab.id, "ts_servidor": salida_ts},
                    tipo="salida",
                    lat=float(sede.lat) + rnd.uniform(-0.0001, 0.0001),
                    lng=float(sede.lng) + rnd.uniform(-0.0001, 0.0001),
                    distancia_m=rnd.uniform(5, 30),
                    sede_id=sede.id,
                    metodo="gps",
                    validacion_estado="ok",
                    sincronizado_offline=False,
                )
                marcas_creadas += 1
    
    db.commit()
    print(f"Semilla OK: {n} trabajadores ficticios, {marcas_creadas} marcas de muestra, usuarios demo: {', '.join(u.email for u in users.values())}")


if __name__ == "__main__":
    main()
