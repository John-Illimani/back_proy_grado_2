from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from django.db import transaction  # 🔥 NUEVO: Transacciones atómicas
from ..serializers.serializer_grades import GradesSerilizer
from ..models.grades_model import Calificaciones
import traceback
import logging

# 🔥 LOGS DETALLADOS
logger = logging.getLogger(__name__)

class GradesListView(generics.ListCreateAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    queryset = Calificaciones.objects.all()
    serializer_class = GradesSerilizer

    def create(self, request, *args, **kwargs):
        data = request.data
        user = request.user

        try:
            # ============================
            # 🔥 CARGA MASIVA (EXCEL)
            # ============================
            if isinstance(data, list):
                logger.info(f"🚀 CARGA MASIVA: {len(data)} registros recibidos")
                
                resultados = []
                fallidos = []
                
                # 🔥 TRANSACCIÓN ATÓMICA: TODO O NADA
                with transaction.atomic():
                    for i, item in enumerate(data):
                        try:
                            logger.info(f"Procesando {i+1}/{len(data)}: estudiante={item.get('estudiante')}")
                            
                            # VALIDAR CAMPOS OBLIGATORIOS
                            estudiante_id = item.get("estudiante")
                            materia_id = item.get("materia")
                            profesor_id = item.get("profesor")
                            
                            if not all([estudiante_id, materia_id, profesor_id]):
                                error = f"Faltan campos: estudiante={estudiante_id}, materia={materia_id}, profesor={profesor_id}"
                                logger.warning(f"❌ Fila {i+1}: {error}")
                                fallidos.append({"fila": i+1, "error": error})
                                continue
                            
                            # 🔥 BUSCAR O CREAR
                            obj, created = Calificaciones.objects.get_or_create(
                                estudiante_id=estudiante_id,
                                materia_id=materia_id,
                                defaults={
                                    'profesor_id': profesor_id,
                                    'notas1': 0,
                                    'notas2': 0,
                                    'notas3': 0,
                                }
                            )
                            
                            # 🔥 ACTUALIZAR SIEMPRE profesor (por si cambió)
                            obj.profesor_id = profesor_id
                            
                            # 🔥 ACTUALIZAR NOTAS (enteros, no float!)
                            if "notas1" in item:
                                obj.notas1 = int(float(item["notas1"]))  # float→int seguro
                            if "notas2" in item:
                                obj.notas2 = int(float(item["notas2"]))
                            if "notas3" in item:
                                obj.notas3 = int(float(item["notas3"]))
                            
                            obj.save()
                            
                            logger.info(f"✅ Fila {i+1}: Guardado ID={obj.id}, notas={obj.notas1}/{obj.notas2}/{obj.notas3}")
                            
                            resultados.append({
                                "exito": True,
                                "id": obj.id,
                                "estudiante": obj.estudiante_id,
                                "materia": obj.materia_id,
                                "profesor": obj.profesor_id,
                                "notas1": obj.notas1,
                                "notas2": obj.notas2,
                                "notas3": obj.notas3,
                                "creado": created
                            })
                            
                        except Exception as e:
                            logger.error(f"💥 Error fila {i+1}: {str(e)}")
                            fallidos.append({"fila": i+1, "error": str(e)})
                            # NO RAISE → continúa con los demás
                            continue
                
                # 🔥 RESPUESTA DETALLADA
                response_data = {
                    "procesados": len(resultados),
                    "fallidos": len(fallidos),
                    "total_enviados": len(data),
                    "resultados": resultados,
                }
                
                if fallidos:
                    response_data["fallidos_detalle"] = fallidos
                
                logger.info(f"🎉 MASIVA FINALIZADA: {len(resultados)} OK, {len(fallidos)} fallidos")
                return Response(response_data, status=status.HTTP_200_OK)

            # ============================
            # 🔥 REGISTRO INDIVIDUAL
            # ============================
            logger.info(f"📝 INDIVIDUAL: {data}")
            
            estudiante_id = data.get("estudiante")
            materia_id = data.get("materia")
            profesor_id = data.get("profesor")

            if not all([estudiante_id, materia_id, profesor_id]):
                return Response(
                    {"error": "Faltan: estudiante, materia, profesor"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            obj, created = Calificaciones.objects.get_or_create(
                estudiante_id=estudiante_id,
                materia_id=materia_id,
                defaults={
                    'profesor_id': profesor_id,
                    'notas1': 0, 'notas2': 0, 'notas3': 0,
                }
            )
            
            obj.profesor_id = profesor_id
            
            if "notas1" in data:
                obj.notas1 = int(float(data["notas1"]))
            if "notas2" in data:
                obj.notas2 = int(float(data["notas2"]))
            if "notas3" in data:
                obj.notas3 = int(float(data["notas3"]))
            
            obj.save()

            logger.info(f"✅ INDIVIDUAL: ID={obj.id}, notas={obj.notas1}/{obj.notas2}/{obj.notas3}")
            
            return Response({
                "message": "Guardado correctamente",
                "id": obj.id,
                "estudiante": obj.estudiante_id,
                "materia": obj.materia_id,
                "profesor": obj.profesor_id,
                "notas1": obj.notas1,
                "notas2": obj.notas2,
                "notas3": obj.notas3,
                "creado": created
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"💥 ERROR GENERAL: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {"error": str(e), "traceback": traceback.format_exc()},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class GradesDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    queryset = Calificaciones.objects.all()
    serializer_class = GradesSerilizer