from django.db import transaction
import joblib
import pandas as pd
import numpy as np
from pathlib import Path
from django.conf import settings
import unicodedata
from .models.tests_model import OpcionRespuesta
from .models.student_model import Estudiante
from .models.majors_model import Carreras
from .models.aptitudes_model import Aptitudes
from .models.grades_model import Calificaciones

# =============================================================================
# 1. CARGA DE TODOS LOS COMPONENTES DEL SISTEMA DE IA ÉLITE
# =============================================================================
try:
    MODELS_DIR = Path(settings.BASE_DIR) / "back_colegio" / "random forest"
    modelo_areas = joblib.load(MODELS_DIR / "modelo_areas_elite.pkl")
    modelo_carreras = joblib.load(MODELS_DIR / "modelo_carreras_elite.pkl")
    feature_encoders = joblib.load(MODELS_DIR / "codificadores_features.pkl")
    le_area = joblib.load(MODELS_DIR / "codificador_objetivo_area.pkl")
    le_carrera = joblib.load(MODELS_DIR / "codificador_objetivo_carrera.pkl")
    
    carreras_bolivia = {
        "Ingeniería y Tecnología": ["Ingeniería Civil", "Ingeniería de Sistemas", "Ingeniería Industrial", 
                                  "Ingeniería Mecánica", "Ingeniería Electrónica", "Ingeniería Química", 
                                  "Arquitectura", "Ingeniería Petrolera"],
        "Ciencias de la Salud": ["Medicina", "Enfermería", "Odontología", "Bioquímica y Farmacia", 
                               "Fisioterapia y Kinesiología", "Nutrición y Dietética"],
        "Ciencias Sociales y Humanidades": ["Derecho", "Psicología", "Comunicación Social", "Trabajo Social", 
                                         "Sociología", "Ciencias de la Educación", "Historia", "Turismo"],
        "Ciencias Económicas y Financieras": ["Administración de Empresas", "Contaduría Pública", 
                                           "Ingeniería Comercial", "Economía", "Ingeniería Financiera"],
        "Ciencias Puras y Naturales": ["Biología", "Física", "Química", "Matemáticas", "Informática", 
                                    "Ingeniería Ambiental"],
        "Artes y Diseño": ["Artes Plásticas", "Música", "Diseño Gráfico y Comunicación Visual", "Diseño de Modas"],
        "Ciencias Agrícolas": ["Ingeniería Agronómica", "Medicina Veterinaria y Zootecnia"],
        "Fuerzas de Seguridad y Defensa": ["Colegio Militar del Ejército", "Colegio Militar de Aviación", 
                                        "Escuela Naval Militar", "Academia Nacional de Policías"]
    }
    print("✅ Servicios de IA: Pipeline Élite cargado correctamente.")
except Exception as e:
    print(f"❌ ERROR al cargar modelos: {str(e)}")
    modelo_areas = None
    modelo_carreras = None
    feature_encoders = {}
    le_area = None
    le_carrera = None

# =============================================================================
# MAPEO DINÁMICO: PALABRAS CLAVE DE MATERIA → APTITUD
# =============================================================================
KEYWORDS_APTITUD = {
    'verbal': {
        'keywords': ['comunicacion', 'lenguaje', 'castellano', 'literatura', 'redaccion', 'lectura', 
                    'ingles', 'idioma', 'oratoria'],
        'peso': 0.30
    },
    'calculo': {
        'keywords': ['matematica', 'fisica', 'quimica', 'calculo', 'algebra', 'geometria', 
                    'estadistica', 'contabilidad', 'finanzas'],
        'peso': 0.30
    },
    'logica_abstracta': {
        'keywords': ['ciencias naturales', 'biologia', 'logica', 'filosofia', 'informatica', 
                    'programacion', 'investigacion'],
        'peso': 0.20
    },
    'mecanico': {
        'keywords': ['tecnica', 'tecnologia', 'taller', 'dibujo', 'mecanica', 'electronica', 
                    'robotica', 'electricidad'],
        'peso': 0.20
    },
    'disciplina_organizacion': {
        'keywords': ['ciencias sociales', 'sociales', 'valores', 'religion', 'etica', 'historia', 
                    'civica', 'administracion'],
        'peso': 0.20
    },
    'liderazgo_social': {
        'keywords': ['educacion fisica', 'deportes', 'musical', 'musica', 'artes', 'psicologia', 
                    'sociologia', 'liderazgo'],
        'peso': 0.20
    }
}

NOTA_MAXIMA = 100.0

def _normalizar_nombre(nombre: str) -> str:
    """Elimina tildes y normaliza texto para búsqueda robusta."""
    if not nombre:
        return ""
    nombre = "".join(c for c in unicodedata.normalize('NFD', str(nombre)) if unicodedata.category(c) != 'Mn')
    return nombre.lower().strip()

def _detectar_aptitud_de_materia(nombre_materia: str) -> tuple:
    nombre_lower = _normalizar_nombre(nombre_materia)
    candidatos = []
    for aptitud, config in KEYWORDS_APTITUD.items():
        for keyword in config['keywords']:
            kw_norm = _normalizar_nombre(keyword)
            if kw_norm in nombre_lower:
                candidatos.append((len(kw_norm), kw_norm, aptitud, config['peso']))
    if not candidatos:
        return None, 0.0
    candidatos.sort(key=lambda x: x[0], reverse=True)
    return candidatos[0][2], candidatos[0][3]

def _calcular_ajuste_por_notas(estudiante_id: int) -> dict:
    """MEJORADO: Búsqueda robusta de calificaciones con debug"""
    try:
        print(f"🔍 Buscando calificaciones para estudiante_id: {estudiante_id}")
        calificaciones = Calificaciones.objects.filter(estudiante_id=estudiante_id).select_related('materia')
        print(f"📊 Encontradas {calificaciones.count()} calificaciones")
        
        if not calificaciones.exists():
            print("⚠️ No se encontraron calificaciones para este estudiante")
            return {}
            
        acumulador = {}
        for calificacion in calificaciones:
            try:
                # MEJORADO: Manejo robusto del nombre de materia
                nombre_materia = getattr(calificacion.materia, 'nombre', None)
                if not nombre_materia:
                    print(f"⚠️ Materia sin nombre: {calificacion.materia}")
                    continue
                    
                aptitud, peso = _detectar_aptitud_de_materia(nombre_materia)
                if aptitud is None:
                    print(f"⚠️ No se detectó aptitud para materia: {nombre_materia}")
                    continue
                    
                # MEJORADO: Manejo robusto del promedio
                promedio = getattr(calificacion, 'promedio', 0)
                if promedio is None:
                    promedio = 0
                    
                nota_normalizada = min(max(promedio / NOTA_MAXIMA, 0), 1)  # Clamp entre 0-1
                
                if aptitud not in acumulador:
                    acumulador[aptitud] = {'suma': 0.0, 'count': 0, 'peso': peso}
                acumulador[aptitud]['suma'] += nota_normalizada
                acumulador[aptitud]['count'] += 1
                
            except Exception as e:
                print(f"❌ Error procesando calificación {calificacion.id}: {str(e)}")
                continue
        
        resultado = {apt: {'promedio': d['suma']/d['count'], 'peso': d['peso']} 
                    for apt, d in acumulador.items()}
        print(f"✅ Ajuste por notas calculado: {resultado}")
        return resultado
        
    except Exception as e:
        print(f"❌ Error en _calcular_ajuste_por_notas: {str(e)}")
        return {}

def _aplicar_ajuste_notas_a_scores(scores_aptitud: pd.DataFrame, ajuste_notas: dict) -> pd.DataFrame:
    scores_ajustados = scores_aptitud.copy()
    for aptitud, datos in ajuste_notas.items():
        if aptitud in scores_ajustados.columns:
            score_original = float(scores_aptitud.loc[0, aptitud])
            promedio_nota = datos['promedio']
            peso = datos['peso']
            score_final = (score_original * (1 - peso)) + (promedio_nota * peso)
            scores_ajustados.loc[0, aptitud] = score_final
            print(f"📈 {aptitud}: {score_original:.3f} → {score_final:.3f} (ajuste: {promedio_nota:.3f})")
    return scores_ajustados

# =============================================================================
# FUNCIÓN PRINCIPAL DEL SERVICIO DE PREDICCIÓN
# =============================================================================
@transaction.atomic
def ejecutar_prediccion_y_guardar(estudiante_id: int):
    """
    MEJORADO: Función principal con manejo robusto de errores y debug completo
    """
    print(f"🚀 Iniciando predicción para estudiante_id: {estudiante_id}")
    
    # Verificación inicial de modelos
    if not all([modelo_areas, modelo_carreras, feature_encoders, le_area, le_carrera]):
        raise RuntimeError("Los modelos de IA no están cargados. Verifique los archivos .pkl")
    
    # --- 0. VERIFICACIÓN Y OBTENCIÓN DEL ESTUDIANTE ---
    try:
        estudiante_obj = Estudiante.objects.get(pk=estudiante_id)
        print(f"✅ Estudiante encontrado: {estudiante_obj}")
    except Estudiante.DoesNotExist:
        print(f"❌ Estudiante con ID {estudiante_id} NO EXISTE en la base de datos")
        raise ValueError(f"El estudiante con ID {estudiante_id} no existe.")
    
    # --- 1. OBTENCIÓN DE RESPUESTAS (ROBUSTO) ---
    try:
        print("🔍 Buscando respuestas del test...")
        respuestas_qs = OpcionRespuesta.objects.filter(estudiante_id=estudiante_id)
        print(f"📊 Encontradas {respuestas_qs.count()} respuestas")
        
        if not respuestas_qs.exists():
            print(f"⚠️ ADVERTENCIA: El estudiante {estudiante_id} no tiene respuestas")
            # Continuar con scores por defecto en lugar de fallar
            respuestas_df_ancho = pd.DataFrame()
        else:
            datos_estudiante = {f'pregunta_{r.pregunta_id}': r.texto for r in respuestas_qs}
            respuestas_df_ancho = pd.DataFrame([datos_estudiante])
            
            # Garantizar todas las columnas esperadas
            columnas_esperadas = [f'pregunta_{i}' for i in range(1, 824)]
            respuestas_df_ancho = respuestas_df_ancho.reindex(columns=columnas_esperadas, fill_value='SIN_RESPUESTA')
            
    except Exception as e:
        print(f"❌ Error obteniendo respuestas: {str(e)}")
        respuestas_df_ancho = pd.DataFrame()
    
    # --- PASO A: Codificación de texto (ROBUSTO) ---
    try:
        if not respuestas_df_ancho.empty:
            for col, le in feature_encoders.items():
                if col in respuestas_df_ancho.columns:
                    valor = str(respuestas_df_ancho.loc[0, col])
                    if valor in le.classes_:
                        respuestas_df_ancho.loc[0, col] = le.transform([valor])[0]
                    else:
                        respuestas_df_ancho.loc[0, col] = -1
            respuestas_df_ancho = respuestas_df_ancho.apply(pd.to_numeric, errors='coerce').fillna(0)
        else:
            # DataFrame vacío: crear con ceros
            columnas_esperadas = [f'pregunta_{i}' for i in range(1, 824)]
            respuestas_df_ancho = pd.DataFrame(0, index=[0], columns=columnas_esperadas)
        print("✅ Codificación completada")
    except Exception as e:
        print(f"❌ Error en codificación: {str(e)}")
        raise
    
    # --- PASO B: Calcular scores de aptitud ---
    map_aptitud_a_preguntas = {
        'verbal': list(range(418, 465)) + list(range(568, 594)),
        'calculo': list(range(465, 505)),
        'logica_abstracta': list(range(505, 553)) + list(range(794, 824)),
        'mecanico': list(range(553, 568)) + list(range(794, 824)),
        'disciplina_organizacion': list(range(99, 183)) + list(range(232, 255)),
        'liderazgo_social': list(range(183, 232)) + list(range(255, 417))
    }
    
    scores_aptitud = pd.DataFrame(index=[0])
    for aptitud, ids_preguntas in map_aptitud_a_preguntas.items():
        columnas = [f'pregunta_{i}' for i in ids_preguntas if f'pregunta_{i}' in respuestas_df_ancho.columns]
        if columnas:
            scores_aptitud[aptitud] = respuestas_df_ancho[columnas].mean(axis=1).fillna(0)
        else:
            scores_aptitud[aptitud] = 0
    print(f"📊 Scores de aptitud calculados: {scores_aptitud.to_dict()}")
    
    # --- PASO B2: Ajustar con calificaciones reales (MEJORADO) ---
    ajuste_notas = _calcular_ajuste_por_notas(estudiante_id)
    if ajuste_notas:
        scores_aptitud = _aplicar_ajuste_notas_a_scores(scores_aptitud, ajuste_notas)
    
    # --- PASO B3: Preparar Aptitudes para JSON ---
    aptitudes_resultado = [
        {"aptitud": apt.replace("_", " ").title(), 
         "porcentaje": f"{float(scores_aptitud.loc[0, apt]) * 100:.2f}%"} 
        for apt in scores_aptitud.columns
    ]
    print(f"✅ Aptitudes finales: {aptitudes_resultado}")
    
    # --- PASO C: Predicciones de IA ---
    try:
        pred_area_num = modelo_areas.predict(scores_aptitud)
        area_principal = le_area.inverse_transform(pred_area_num)[0]
        
        probabilidades_carreras = modelo_carreras.predict_proba(scores_aptitud)[0]
        ranking_global = sorted(
            zip(le_carrera.classes_, probabilidades_carreras),
            key=lambda item: item[1],
            reverse=True
        )
        print(f"🌟 Área principal predicha: {area_principal}")
        print(f"📈 Top 5 carreras predichas: {ranking_global[:5]}")
        
    except Exception as e:
        print(f"❌ Error en predicción de IA: {str(e)}")
        raise
    
    # --- PASO D: Filtrado y Garantía de Top 3 ---
    carreras_del_area = carreras_bolivia.get(area_principal, [])
    recomendaciones_finales = [
        {"carrera": c, "probabilidad": f"{p:.2%}"} 
        for c, p in ranking_global if c in carreras_del_area
    ][:3]
    
    # Rellenar si es necesario
    if len(recomendaciones_finales) < 3:
        ya_incluidas = [r["carrera"] for r in recomendaciones_finales]
        for carrera, prob in ranking_global:
            if len(recomendaciones_finales) >= 3:
                break
            if carrera not in ya_incluidas:
                recomendaciones_finales.append({"carrera": carrera, "probabilidad": f"{prob:.2%}"})
    
    print(f"✅ Recomendaciones finales: {recomendaciones_finales}")
    
    # --- 3. GUARDADO FINAL EN BASE DE DATOS ---
    try:
        # Guardar Carreras
        Carreras.objects.update_or_create(
            estudiante=estudiante_obj,
            defaults={'carreras': recomendaciones_finales}
        )
        
        # Guardar Aptitudes
        Aptitudes.objects.update_or_create(
            estudiante=estudiante_obj,
            defaults={'aptitudes': aptitudes_resultado}
        )
        
        print(f"✅ PROCESO COMPLETADO EXITOSAMENTE para Estudiante ID: {estudiante_id}")
        print(f"💾 Datos guardados correctamente en la base de datos")
        
    except Exception as e:
        print(f"❌ Error guardando en BD: {str(e)}")
        raise
    
    return {
        'aptitudes': aptitudes_resultado,
        'area_principal': area_principal,
        'recomendaciones': recomendaciones_finales,
        'ajuste_notas': ajuste_notas
    }