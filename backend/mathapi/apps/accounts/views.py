from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from .serializers import (
    CustomTokenObtainPairSerializer, UserSerializer,
    UserCreateSerializer, ChangePasswordSerializer
)
from .models import AuditLog

User = get_user_model()


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            user = User.objects.get(email=request.data.get('email'))
            AuditLog.objects.create(
                user=user,
                action=AuditLog.Action.LOGIN,
                model_name='User',
                object_id=str(user.id),
                description=f'User logged in',
                ip_address=get_client_ip(request),
            )
        return response


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            token = RefreshToken(refresh_token)
            token.blacklist()
            AuditLog.objects.create(
                user=request.user,
                action=AuditLog.Action.LOGOUT,
                model_name='User',
                object_id=str(request.user.id),
                description='User logged out',
                ip_address=get_client_ip(request),
            )
            return Response({'detail': 'Logged out successfully.'}, status=status.HTTP_200_OK)
        except Exception:
            return Response({'detail': 'Invalid token.'}, status=status.HTTP_400_BAD_REQUEST)


class RegisterView(generics.CreateAPIView):
    serializer_class = UserCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        # Only admins and teachers can create users
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    def perform_create(self, serializer):
        user = serializer.save()
        AuditLog.objects.create(
            user=self.request.user,
            action=AuditLog.Action.CREATE,
            model_name='User',
            object_id=str(user.id),
            description=f'Created user {user.email}',
            ip_address=get_client_ip(self.request),
        )


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                {'old_password': 'Incorrect password.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({'detail': 'Password changed successfully.'})


class UserListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['role', 'is_active']
    search_fields = ['email', 'first_name', 'last_name']

    def get_queryset(self):
        user = self.request.user
        if user.role in ['super_admin', 'teacher']:
            return User.objects.all().order_by('first_name')
        return User.objects.filter(id=user.id)


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')


class SiteSettingsView(APIView):
    """GET: public. PATCH: admin only."""

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get(self, request):
        from .models import SiteSettings
        from .serializers import SiteSettingsSerializer
        try:
            obj = SiteSettings.get()
            return Response(SiteSettingsSerializer(obj).data)
        except Exception as e:
            # Return safe defaults if DB schema is incomplete (pre-migration)
            return Response({
                'platform_name': 'MathPlatform',
                'platform_subtitle': 'Tanzania',
                'logo_url': '',
                'logo_letter': 'Σ',
                'favicon_url': '',
                'footer_text': '© 2025 MathPlatform · Built for Tanzanian Secondary Schools',
                'login_tagline': 'Student Performance Analytics',
                'login_welcome': 'Sign in to your account',
                'login_bg_gradient': True,
                'page_settings': {},
            })

    def patch(self, request):
        from .models import SiteSettings
        from .serializers import SiteSettingsSerializer
        user = request.user
        if not user.is_authenticated or user.role != 'super_admin':
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            obj = SiteSettings.get()
            serializer = SiteSettingsSerializer(obj, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            instance = serializer.save(updated_by=user)
            return Response(SiteSettingsSerializer(instance).data)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            # Return JSON so the frontend can display the real error instead of HTML 500
            return Response(
                {'detail': str(e), 'traceback': tb},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
