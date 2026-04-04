

from rest_framework import generics
from ..serializers.serializer_user import UserSerializer
from ..models.usuario_model import Usuario
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from ..serializers.serializer_user import UserSerializer


from ..models.student_model import Estudiante 
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated


class UserlListView(generics.ListCreateAPIView):
    # jwt que esta lista solo puedan ver los usuarios autenticados
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    queryset = Usuario.objects.all()
    serializer_class = UserSerializer


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    queryset = Usuario.objects.all()
    serializer_class = UserSerializer


# NUEVA VISTA PARA CARGA MASIVA
class UserBulkCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        usuarios_datos = request.data
        if not isinstance(usuarios_datos, list):
            return Response({"error": "Se esperaba una lista de datos"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                for data in usuarios_datos:
                    paralelo_id = data.pop('paralelo', None)
                    
                    # 1. Intentamos buscar si el Usuario ya existe por su nombre/apellido 
                    # o mejor aún, dejamos que el Serializer maneje la creación del User.
                    # Si el UserSerializer lanza error de username duplicado, lo capturamos.
                    
                    serializer = UserSerializer(data=data)
                    if serializer.is_valid(raise_exception=True):
                        nuevo_usuario = serializer.save()
                        
                        # 2. 🔥 SOLUCIÓN AL ERROR DE LLAVE DUPLICADA:
                        # Usamos 'update_or_create' para que si el usuario_id ya existe en Estudiante,
                        # solo actualice el paralelo en lugar de intentar crear uno nuevo.
                        if paralelo_id:
                            Estudiante.objects.update_or_create(
                                usuario=nuevo_usuario,
                                defaults={'paralelo_id': paralelo_id}
                            )
                
            return Response({"message": f"Se procesaron {len(usuarios_datos)} registros correctamente"}, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            # Si el error es de base de datos, mostramos un mensaje más limpio
            error_msg = str(e)
            if "already exists" in error_msg or "ya existe la llave" in error_msg:
                return Response({"error": "Uno de los usuarios ya está registrado o el username está duplicado."}, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({"error": error_msg}, status=status.HTTP_400_BAD_REQUEST)