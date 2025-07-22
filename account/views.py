from rest_framework import generics, permissions, status
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate
from .serializers import (
    RegisterSerializer, 
    EmailVerificationSerializer, 
    ResendVerificationSerializer,
    GoogleAuthSerializer,
    UserSerializer
)
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from .models import EmailVerificationToken
from django.contrib.auth import authenticate
from .utils import send_verification_email_with_api
import secrets, string
import uuid

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
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            token_uuid = serializer.validated_data['token']
            print(f"Attempting to verify token: {token_uuid}")
            
            try:
                token = EmailVerificationToken.objects.get(
                    token=token_uuid,
                    is_used=False
                )
                print(f"Found token for user: {token.user.email}")
                
                # Check if token is expired
                if token.is_expired():
                    print(f"Token is expired. Created: {token.created_at}, Expires: {token.expires_at}")
                    return Response({
                        'error': 'Verification token has expired. Please request a new one.'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Check if user is already verified
                user = token.user
                if user.is_email_verified:
                    print(f"User {user.email} is already verified")
                    # Mark token as used even if already verified
                    token.is_used = True
                    token.save()
                    
                    return Response({
                        'message': 'Email is already verified! You can now log in.'
                    }, status=status.HTTP_200_OK)
                
                # Mark user as verified
                user.is_email_verified = True
                user.save()
                print(f"User {user.email} marked as verified")
                
                # Mark token as used
                token.is_used = True
                token.save()
                print(f"Token marked as used")
                
                return Response({
                    'message': 'Email verified successfully! You can now log in.'
                }, status=status.HTTP_200_OK)
                
            except EmailVerificationToken.DoesNotExist:
                print(f"Token not found in database: {token_uuid}")
                
                # Check if there's a user with this email that's already verified
                # This can happen if the admin manually verified the user
                try:
                    # Try to find any token (used or unused) with this UUID
                    used_token = EmailVerificationToken.objects.get(token=token_uuid)
                    if used_token.user.is_email_verified:
                        print(f"Found used token for already verified user: {used_token.user.email}")
                        return Response({
                            'message': 'Email is already verified! You can now log in.'
                        }, status=status.HTTP_200_OK)
                except EmailVerificationToken.DoesNotExist:
                    pass
                
                return Response({
                    'error': 'Invalid or expired verification token. Please request a new verification email.'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            print(f"Unexpected error in email verification: {str(e)}")
            return Response({
                'error': 'An error occurred during verification. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
                    'message': 'Email is already verified. You can log in now.'
                }, status=status.HTTP_200_OK)
            
            # Delete old unused tokens for this user
            EmailVerificationToken.objects.filter(user=user, is_used=False).delete()
            
            # Send new verification email
            if send_verification_email_with_api(user):
                return Response({
                    'message': 'Verification email sent successfully. Please check your inbox.'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': 'Failed to send verification email. Please try again later.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except User.DoesNotExist:
            return Response({
                'error': 'User with this email does not exist.'
            }, status=status.HTTP_404_NOT_FOUND)

class ProfileView(generics.RetrieveUpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
    
@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    try:
        data = request.data

        email = data.get('email') or data.get('username')  
        password = data.get('password')

        if not email or not password:
            return Response({
                'detail': 'Email and password are required',
                'received_fields': list(data.keys())
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Try to get user by email
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({
                'detail': 'Invalid email or password'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Check if email is verified
        if not user.is_email_verified:
            return Response({
                'detail': 'Please verify your email before logging in. Check your inbox for a verification link.',
                'email_verified': False,
                'user_email': user.email
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Authenticate user using username and password
        authenticated_user = authenticate(username=user.username, password=password)
        
        if authenticated_user:
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'name': f"{user.first_name} {user.last_name}".strip() or user.username,
                    'is_email_verified': user.is_email_verified,
                }
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'detail': 'Invalid email or password'
            }, status=status.HTTP_401_UNAUTHORIZED)
            
    except Exception as e:
        import traceback
        print(f"Login error: {str(e)}")
        print(traceback.format_exc())
        return Response({
            'detail': 'An error occurred during login',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GoogleAuthView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = GoogleAuthSerializer
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Get user info from Google
        user_data = serializer.validated_data['token']
        
        email = user_data.get('email')
        given_name = user_data.get('given_name', '')
        family_name = user_data.get('family_name', '')
        google_id = user_data.get('google_id')
        picture = user_data.get('picture', '')
        
        # Generate username from email if names are not provided
        username = email.split('@')[0] if email else 'user'
        full_name = f"{given_name} {family_name}".strip()
        if not full_name:
            full_name = username
        
        try:
            # Check if user exists by email
            user = User.objects.get(email=email)
            
            # Link Google account if not already linked
            if not user.google_id:
                user.google_id = google_id
                user.is_email_verified = True
                if not user.first_name and given_name:
                    user.first_name = given_name
                if not user.last_name and family_name:
                    user.last_name = family_name
                user.save()
                
        except User.DoesNotExist:
            # Create new user
            random_password = ''.join(secrets.choice(
                string.ascii_letters + string.digits
            ) for _ in range(12))
            
            # Ensure unique username
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=given_name,
                last_name=family_name,
                password=random_password,
                is_email_verified=True,
                google_id=google_id
            )
            
            # Create user profile
            from .models import UserProfile
            UserProfile.objects.create(user=user)
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'name': full_name,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_email_verified': user.is_email_verified,
            }
        }, status=status.HTTP_200_OK)