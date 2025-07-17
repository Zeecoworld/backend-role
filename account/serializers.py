from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import UserProfile
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .utils import send_verification_email_with_api
from google.oauth2 import id_token
from django.conf import settings
from rest_framework import serializers
from django.contrib.auth import authenticate, get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from google.auth.transport import requests

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('username', 'email', 'password')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        user.is_active = True  # User is created but not verified
        user.save()
        
        # Create user profile
        UserProfile.objects.create(user=user)
        
        # Send verification email
        send_verification_email_with_api(user)
        
        return user
    
class EmailVerificationSerializer(serializers.Serializer):
    token = serializers.UUIDField()

class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ('profile_picture', 'bio')

class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'profile')

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', {})
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        profile = instance.profile
        for attr, value in profile_data.items():
            setattr(profile, attr, value)
        profile.save()
        return instance
    
    
class GoogleAuthSerializer(serializers.Serializer):
    token = serializers.CharField()
    
    def validate_token(self, value):
        try:
            # Verify the Google token
            idinfo = id_token.verify_oauth2_token(
                value, 
                requests.Request(), 
                settings.GOOGLE_OAUTH2_CLIENT_ID
            )
            
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise serializers.ValidationError('Invalid token issuer')
            
            return {
                'email': idinfo.get('email'),
                'given_name': idinfo.get('given_name', ''),
                'family_name': idinfo.get('family_name', ''),
                'google_id': idinfo.get('sub'),
                'email_verified': idinfo.get('email_verified', False),
                'picture': idinfo.get('picture', ''),
            }
            
        except ValueError as e:
            raise serializers.ValidationError(f'Invalid Google token: {str(e)}')
