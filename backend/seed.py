"""Semilla ficticia y anonimizada (idempotente). Ver README: patrones derivados del Excel de referencia.
NO contiene nombres, DNI ni sueldos reales. Uso: python seed.py [--if-empty]
--if-empty: no hace nada si ya existen usuarios (lo usa start.sh con AUTO_SEED=1 en dev).
--config-only: solo configuración (tipos de contrato, empresas y reglas casi reales); apta para prod (SEED_CONFIG=1).
La semilla demo (trabajadores, marcas, usuarios demo) se niega a correr con APP_ENV=production."""
import os
import random
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from zoneinfo import ZoneInfo

from app.config import settings
from app.db import SessionLocal
from app.models import (
    Asistencia,
    BancoHorasCompensatorias,
    BonoNocturno,
    BonoNocturnoHistorial,
    Empresa,
    HorarioPlan,
    Marca,
    RegularizacionHE,
    RuleSet,
    Sede,
    TipoContrato,
    Trabajador,
    TurnoPlantilla,
    Unidad,
    Usuario,
)
from app.rules import CAVAS, CAVAS_DEMO, CAVAS_REAL_DESDE, GCB_SA
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


# RUC verificado (sprint 5) en consulta pública de padrón SUNAT: GRUPO CORDILLERA BLANCA SOCIEDAD ANONIMA, activo/habido.
RUC_GCBSA = "20605363882"
# CAVAS: confirmado por el PO (2026-10-30): CAVAS REUNIDAS PERU SOCIEDAD ANONIMA; el codigo corto "CAVAS" se mantiene.
RUC_CAVAS = "20610414983"
RAZON_CAVAS = "CAVAS REUNIDAS PERU S.A."


def rs_vigente(db, empresa_id, dia):
    """rule_set vigente al día (si es anterior a todas las vigencias, la primera)."""
    q = select(RuleSet.id).where(RuleSet.empresa_id == empresa_id)
    return (db.scalar(q.where(RuleSet.valid_from <= dia).order_by(RuleSet.valid_from.desc()).limit(1))
            or db.scalar(q.order_by(RuleSet.valid_from).limit(1)))


def get_or_create(db, model, where: dict, **extra):
    obj = db.scalar(select(model).filter_by(**where))
    if not obj:
        obj = model(**where, **extra)
        db.add(obj)
        db.flush()
    return obj


def main():
    if os.getenv("APP_ENV", "").lower() in ("prod", "production"):
        raise SystemExit("Semilla DEMO bloqueada: APP_ENV=production. Use --config-only.")
    db = SessionLocal()
    tc, cav, gcb = seed_config(db, demo=True)
    _seed_demo(db, tc, cav, gcb)


def seed_config(db, demo: bool = False):
    """Configuración base idempotente (sin datos personales): tipos de contrato, empresas y rule_sets.
    No sobrescribe lo editado luego en el módulo Configuración: solo crea lo que falta; los rule_set
    se crean únicamente si la empresa aún no tiene ninguno (prod) o si falta la vigencia (dev)."""
    tc = {c: get_or_create(db, TipoContrato, {"codigo": c}, nombre=n, horas_mes=h, jornada_diaria_min=j, es_part_time=pt,
                           refrigerio_min=45)  # PO: refrigerio 45 min también para PT85/PT102
          for c, n, h, j, pt in [("FT", "Tiempo completo", 208, 480, False), ("PT85", "Part time 85 h/mes", 85, 240, True),
                                 ("PT102", "Part time 102 h/mes", 102, 240, True)]}
    cav = get_or_create(db, Empresa, {"codigo": "CAVAS"}, razon_social=RAZON_CAVAS, ruc=RUC_CAVAS)
    gcb = get_or_create(db, Empresa, {"codigo": "GCBSA"}, razon_social="GCB SA", ruc=RUC_GCBSA)
    if demo:
        for e, cfg in ((cav, CAVAS_DEMO), (gcb, GCB_SA)):
            get_or_create(db, RuleSet, {"empresa_id": e.id, "version": 1}, valid_from=date(2026, 1, 1), config=cfg,
                          motivo="Demo/legado (Sprint 1)" if e is cav else "Reglas confirmadas Sprint 1")
    elif not db.scalar(select(RuleSet.id).where(RuleSet.empresa_id == gcb.id).limit(1)):
        db.add(RuleSet(empresa_id=gcb.id, version=1, valid_from=date(2026, 1, 1), config=GCB_SA,
                       motivo="Semilla prod: reglas confirmadas GCB SA"))
    # Reglas reales CAVAS (PO) vigentes desde 2026-11-01. Idempotente; crear un rule_set no recalcula nada.
    tiene = select(RuleSet.id).where(RuleSet.empresa_id == cav.id)
    if not db.scalar((tiene.where(RuleSet.valid_from == CAVAS_REAL_DESDE) if demo else tiene).limit(1)):
        ver = (db.scalar(select(func.max(RuleSet.version)).where(RuleSet.empresa_id == cav.id)) or 0) + 1
        db.add(RuleSet(empresa_id=cav.id, version=ver, valid_from=CAVAS_REAL_DESDE, config=CAVAS,
                       motivo="Reglas reales CAVAS (PO): tolerancia 10, corte 06:00, HE pago, nocturno aparte"))
    db.flush()
    return tc, cav, gcb


def _seed_demo(db, tc, cav, gcb):
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
    
    # Sprint 3: marcas del trabajador demo (trabajador@demo.gcb.pe → CAV-007) para "Mis marcas":
    # turno nocturno que cruza el corte 06:00 (salida 02:xx pertenece al día operativo anterior), una por QR y una fuera de geocerca.
    lima = ZoneInfo("America/Lima")
    demo = db.scalar(select(Trabajador).where(Trabajador.codigo == "CAV-007"))
    if demo:
        for dia_offset in range(1, 6):
            dia = hoy - timedelta(days=dia_offset)
            ent = datetime.combine(dia, time(19, rnd.randint(0, 10)), lima)
            sal = datetime.combine(dia + timedelta(days=1), time(2, rnd.randint(0, 20)), lima)
            fuera = dia_offset == 3
            for tipo, ts in (("entrada", ent), ("salida", sal)):
                qr = tipo == "entrada" and dia_offset == 2
                get_or_create(db, Marca, {"trabajador_id": demo.id, "ts_servidor": ts}, tipo=tipo,
                              lat=float(s_cav.lat) + (0.003 if fuera and tipo == "salida" else 0.00005),
                              lng=float(s_cav.lng), distancia_m=335.0 if fuera and tipo == "salida" else 6.0, sede_id=s_cav.id,
                              metodo="qr" if qr else "gps", qr_code="SEDE-SISA-FICT" if qr else None,
                              validacion_estado="fuera_geocerca" if fuera and tipo == "salida" else "ok",
                              sincronizado_offline=False)
                marcas_creadas += 1

    # Sprint 3 / Incremento 2: casos de ejemplo para Excepciones y Bolsa de horas.
    # Idempotente: se omite si ya existe algún movimiento de banco con origen "Seed:".
    if not db.scalar(select(BancoHorasCompensatorias.id).where(BancoHorasCompensatorias.origen.like("Seed:%")).limit(1)):
        seed_excepciones(db, hoy, users)
    # Sprint 3 / Incremento 3: turnos nocturnos con HE y bono 3 AM para la pantalla Reportes (idempotente).
    if not db.scalar(select(BonoNocturno.id).where(BonoNocturno.observacion.like("Seed:%")).limit(1)):
        seed_reportes(db, hoy, users)
    # Incremento 4: monto de ejemplo del bono 3 AM (idempotente: sólo si el bono seed aún no tiene monto).
    for b in db.scalars(select(BonoNocturno).where(BonoNocturno.observacion.like("Seed:%"), BonoNocturno.monto.is_(None))):
        b.monto, b.aprobado_por = Decimal("60.00"), users["rrhh"].id
        db.add(BonoNocturnoHistorial(bono_id=b.id, usuario_id=users["admin"].id, accion="corregir", cantidad=b.cantidad,
                                     monto=b.monto, estado=b.estado, comentario="Seed: monto de ejemplo S/ 60.00"))

    db.commit()
    print(f"Semilla OK: {n} trabajadores ficticios, {marcas_creadas} marcas de muestra, usuarios demo: {', '.join(u.email for u in users.values())}")


def seed_excepciones(db, hoy: date, users: dict):
    """Asistencias calculadas de ejemplo + bandeja HE (pendiente/aprobada/rechazada) + bolsa de horas + alerta PT."""
    trab = {t.codigo: t for t in db.scalars(select(Trabajador).where(
        Trabajador.codigo.in_(["CAV-001", "CAV-002", "CAV-007", "CAV-009", "PAR-001", "PAR-002"])))}
    def asis(cod, dias_atras, prog, trab_h, exceso=0.0, tardanza=0):
        t = trab[cod]
        d = hoy - timedelta(days=dias_atras)
        rs = {t.empresa_id: rs_vigente(db, t.empresa_id, d)}
        return get_or_create(db, Asistencia, {"trabajador_id": t.id, "dia_operativo": d}, periodo=d.strftime("%Y-%m"),
                             horas_programadas=prog, horas_trabajadas=trab_h, tardanza_min=tardanza, horas_extra_25=0,
                             horas_extra_35=0, horas_nocturnas=0, exceso_no_programado=exceso, rule_set_id=rs[t.empresa_id])

    def reg(a, horas, estado="pendiente", destino=None, obs=None):
        r = get_or_create(db, RegularizacionHE, {"asistencia_id": a.id}, trabajador_id=a.trabajador_id, horas_exceso=horas,
                          estado=estado, destino=destino, observacion=obs,
                          decision_por=users["jefe"].id if estado != "pendiente" else None,
                          decision_en=datetime.now(ZoneInfo("America/Lima")) if estado != "pendiente" else None)
        return r

    def mov(cod, dias_atras, tipo, horas, saldo_ant, origen, reg_id=None, expira_en=None):
        t = trab[cod]
        db.add(BancoHorasCompensatorias(
            trabajador_id=t.id, fecha_movimiento=hoy - timedelta(days=dias_atras), tipo=tipo, horas=horas,
            saldo_anterior=saldo_ant, saldo_nuevo=saldo_ant + (horas if tipo == "credito" else -horas), origen=origen,
            regularizacion_id=reg_id, dias_expiracion=90 if tipo == "credito" else None,
            fecha_expira=hoy + timedelta(days=expira_en) if expira_en is not None else None))
        db.flush()

    # CAV-009 (PT85): semana con 6.5 h/día -> alerta PT (no bloquea) + HE pendiente
    for k in range(2, 7):
        a = asis("CAV-009", k, 4.0, 6.5 if k != 2 else 5.5, exceso=1.5 if k == 2 else 0.0)
        if k == 2:
            reg(a, 1.5)
    # CAV-007 (usuario trabajador demo): bolsa con crédito y descanso tomado -> saldo 2 h
    mov("CAV-007", 40, "credito", 3.0, 0.0, "Seed: HE compensatoria aprobada (ejemplo)", expira_en=50)
    mov("CAV-007", 10, "debito", 1.0, 3.0, "Seed: Descanso compensatorio tomado (ejemplo)")
    # CAV-001 (FT, Cavas -> default pago): HE pendiente + tardanza
    reg(asis("CAV-001", 1, 8.0, 10.5, exceso=2.5, tardanza=12), 2.5)
    # CAV-002: exceso rechazado por el jefe
    reg(asis("CAV-002", 3, 8.0, 9.0, exceso=1.0), 1.0, "rechazado", None, "No fue solicitado (ejemplo)")
    # PAR-001 (GCB SA -> default compensación): HE pendiente
    reg(asis("PAR-001", 1, 8.0, 11.0, exceso=3.0), 3.0)
    # PAR-002: HE aprobada a compensación -> crédito en bolsa, por vencer en 20 días
    r = reg(asis("PAR-002", 15, 8.0, 10.0, exceso=0.0), 2.0, "aprobado", "compensacion", "Compensa el lunes (ejemplo)")
    mov("PAR-002", 15, "credito", 2.0, 0.0, f"Seed: HE compensatoria aprobada (reg #{r.id})", reg_id=r.id, expira_en=20)

def seed_reportes(db, hoy: date, users: dict):
    """Turno 22:00-07:00 (HE 25% + horas nocturnas) en CAVAS (recargo aparte) y GCB SA (sin recargo) + bono 3 AM aprobado."""
    for cod in ("CAV-003", "PAR-001"):
        t = db.scalar(select(Trabajador).where(Trabajador.codigo == cod))
        if not t:
            continue
        d = hoy - timedelta(days=2)
        rs = rs_vigente(db, t.empresa_id, d)
        get_or_create(db, Asistencia, {"trabajador_id": t.id, "dia_operativo": d}, periodo=d.strftime("%Y-%m"),
                      horas_programadas=8, horas_trabajadas=9, tardanza_min=0, horas_extra_programadas=1,
                      horas_extra_25=1, horas_extra_35=0, horas_nocturnas=8, exceso_no_programado=0, rule_set_id=rs)
        if cod == "CAV-003":
            get_or_create(db, BonoNocturno, {"trabajador_id": t.id, "periodo": d.strftime("%Y-%m")}, cantidad=2,
                          monto=Decimal("60.00"), estado="aprobado", observacion="Seed: cierres 3 AM (ejemplo)",
                          registrado_por=users["admin"].id, aprobado_por=users["rrhh"].id)
    db.flush()


def base_vacia() -> bool:
    with SessionLocal() as db:
        return db.scalar(select(Usuario.id).limit(1)) is None


if __name__ == "__main__":
    if "--config-only" in sys.argv[1:]:
        with SessionLocal() as s:
            seed_config(s)
            s.commit()
        print("Semilla de configuración aplicada (idempotente)")
    elif "--if-empty" in sys.argv[1:] and not base_vacia():
        print("Semilla omitida: la base ya tiene datos")
    else:
        main()
