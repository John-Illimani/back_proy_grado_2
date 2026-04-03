from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated

from ..serializers.serializer_grades import GradesSerilizer
from ..models.grades_model import Calificaciones

import traceback


class GradesListView(generics.ListCreateAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    queryset = Calificaciones.objects.all()
    serializer_class = GradesSerilizer

    def create(self, request, *args, **kwargs):
        data = request.data

        try:
            # ============================
            # 🔥 CARGA MASIVA (EXCEL)
            # ============================
            if isinstance(data, list):
                resultados = []

                for item in data:
                    estudiante_id = item.get("estudiante")
                    materia_id = item.get("materia")

                    if not estudiante_id or not materia_id:
                        continue

                    obj = Calificaciones.objects.filter(
                        estudiante_id=estudiante_id,
                        materia_id=materia_id
                    ).first()

                    if not obj:
                        obj = Calificaciones.objects.create(
                            estudiante_id=estudiante_id,
                            materia_id=materia_id,
                            notas1=0,
                            notas2=0,
                            notas3=0
                        )

                    # 🔥 SOLO ACTUALIZA LO QUE VIENE
                    if "notas1" in item:
                        obj.notas1 = float(item.get("notas1", obj.notas1))

                    if "notas2" in item:
                        obj.notas2 = float(item.get("notas2", obj.notas2))

                    if "notas3" in item:
                        obj.notas3 = float(item.get("notas3", obj.notas3))

                    obj.save()

                    resultados.append({
                        "estudiante": obj.estudiante_id,
                        "materia": obj.materia_id,
                        "notas1": obj.notas1,
                        "notas2": obj.notas2,
                        "notas3": obj.notas3
                       
                    })

                return Response(
                    {
                        "procesados": len(resultados),
                        "resultados": resultados
                    },
                    status=status.HTTP_200_OK
                )

            # ============================
            # 🔥 REGISTRO INDIVIDUAL
            # ============================
            estudiante_id = data.get("estudiante")
            materia_id = data.get("materia")

            if not estudiante_id or not materia_id:
                return Response(
                    {"error": "estudiante y materia son requeridos"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            obj = Calificaciones.objects.filter(
                estudiante_id=estudiante_id,
                materia_id=materia_id
            ).first()

            if not obj:
                obj = Calificaciones.objects.create(
                    estudiante_id=estudiante_id,
                    materia_id=materia_id,
                    notas1=0,
                    notas2=0,
                    notas3=0
                )

            # 🔥 SOLO ACTUALIZA LO QUE VIENE
            if "notas1" in data:
                obj.notas1 = float(data.get("notas1", obj.notas1))

            if "notas2" in data:
                obj.notas2 = float(data.get("notas2", obj.notas2))

            if "notas3" in data:
                obj.notas3 = float(data.get("notas3", obj.notas3))

            obj.save()

            return Response(
                {
                    "message": "Guardado correctamente",
                    "id": obj.id,
                    "estudiante": obj.estudiante_id,
                    "materia": obj.materia_id,
                    "notas1": obj.notas1,
                    "notas2": obj.notas2,
                    "notas3": obj.notas3
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            print("❌ ERROR GENERAL:", str(e))
            traceback.print_exc()

            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GradesDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    queryset = Calificaciones.objects.all()
    serializer_class = GradesSerilizer