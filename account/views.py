from rest_framework import generics, permissions, status
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth import get_user_model
from .serializers import (
    RegisterSerializer, 
    EmailVerificationSerializer, 
    ResendVerificationSerializer,
    CustomTokenObtainPairSerializer,
    GoogleAuthSerializer,
    UserSerializer
)
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from .models import EmailVerificationToken
from .utils import send_verification_email_with_api
import secrets,string


User = get_user_model()

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegisterSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        return Response({
            'message': 'Registration successful! Please check your email to verify your account.',
            'email': user.email
        }, status=status.HTTP_201_CREATED)

class EmailVerificationView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = EmailVerificationSerializer
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        token_uuid = serializer.validated_data['token']
        
        try:
            token = EmailVerificationToken.objects.get(
                token=token_uuid,
                is_used=False
            )
            
            if token.is_expired():
                return Response({
                    'error': 'Verification token has expired. Please request a new one.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Mark user as verified
            user = token.user
            user.is_email_verified = True
            user.save()
            
            # Mark token as used
            token.is_used = True
            token.save()
            
            return Response({
                'message': 'Email verified successfully! You can now log in.'
            }, status=status.HTTP_200_OK)
            
        except EmailVerificationToken.DoesNotExist:
            return Response({
                'error': 'Invalid verification token.'
            }, status=status.HTTP_400_BAD_REQUEST)

class ResendVerificationView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = ResendVerificationSerializer
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
            
            if user.is_email_verified:
                return Response({
                    'message': 'Email is already verified.'
                }, status=status.HTTP_200_OK)
            
            # Send new verification email
            if send_verification_email_with_api(user):
                return Response({
                    'message': 'Verification email sent successfully.'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': 'Failed to send verification email.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except User.DoesNotExist:
            return Response({
                'error': 'User with this email does not exist.'
            }, status=status.HTTP_404_NOT_FOUND)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class ProfileView(generics.RetrieveUpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    

    def get_object(self):
        return self.request.user
    

class GoogleAuthView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = GoogleAuthSerializer
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Get user info from Google
        user_data = serializer.validated_data['token']
        
        email = user_data.get('email')
        first_name = user_data.get('first_name')
        last_name = user_data.get('last_name')
        google_id = user_data.get('google_id')
        
        try:
            # Check if user exists
            user = User.objects.get(email=email)
            
            # Link Google account if not already linked
            if not user.google_id:
                user.google_id = google_id
                user.is_email_verified = True
                user.save()
                
        except User.DoesNotExist:
            # Create new user
            random_password = ''.join(secrets.choice(
                string.ascii_letters + string.digits
            ) for _ in range(12))
            
            user = User.objects.create_user(
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=random_password,
                is_email_verified=True,
                google_id=google_id
            )
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_email_verified': user.is_email_verified,
            }
        }, status=status.HTTP_200_OK)

