import json
import uuid
from unittest.mock import patch, Mock
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from .models import EmailVerificationToken, UserProfile
from .utils import send_verification_email_with_api


User = get_user_model()


class RegisterViewTest(APITestCase):
    def setUp(self):
        self.register_url = reverse('register')  # Adjust URL name as needed
        self.valid_payload = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass123'
        }

    @patch('your_app.views.send_verification_email_with_api')
    def test_register_user_success(self, mock_send_email):
        """Test successful user registration"""
        mock_send_email.return_value = True
        
        response = self.client.post(self.register_url, self.valid_payload)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['email'], 'test@example.com')
        self.assertIn('Registration successful', response.data['message'])
        
        # Verify user was created
        self.assertTrue(User.objects.filter(email='test@example.com').exists())
        user = User.objects.get(email='test@example.com')
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_email_verified)
        
        # Verify UserProfile was created
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        
        # Verify email was sent
        mock_send_email.assert_called_once_with(user)

    def test_register_user_invalid_email(self):
        """Test registration with invalid email"""
        payload = self.valid_payload.copy()
        payload['email'] = 'invalid-email'
        
        response = self.client.post(self.register_url, payload)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_register_user_missing_fields(self):
        """Test registration with missing required fields"""
        payload = {'email': 'test@example.com'}
        
        response = self.client.post(self.register_url, payload)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)
        self.assertIn('password', response.data)

    def test_register_user_duplicate_email(self):
        """Test registration with duplicate email"""
        User.objects.create_user(
            username='existing',
            email='test@example.com',
            password='pass123'
        )
        
        response = self.client.post(self.register_url, self.valid_payload)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class EmailVerificationViewTest(APITestCase):
    def setUp(self):
        self.verification_url = reverse('email-verification')  # Adjust URL name as needed
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            is_email_verified=False
        )
        self.token = EmailVerificationToken.objects.create(user=self.user)

    def test_email_verification_success(self):
        """Test successful email verification"""
        payload = {'token': str(self.token.token)}
        
        response = self.client.post(self.verification_url, payload)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Email verified successfully', response.data['message'])
        
        # Verify user is now verified
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)
        
        # Verify token is marked as used
        self.token.refresh_from_db()
        self.assertTrue(self.token.is_used)

    def test_email_verification_invalid_token(self):
        """Test email verification with invalid token"""
        payload = {'token': str(uuid.uuid4())}
        
        response = self.client.post(self.verification_url, payload)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid verification token', response.data['error'])

    def test_email_verification_used_token(self):
        """Test email verification with already used token"""
        self.token.is_used = True
        self.token.save()
        
        payload = {'token': str(self.token.token)}
        
        response = self.client.post(self.verification_url, payload)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid verification token', response.data['error'])

    @patch.object(EmailVerificationToken, 'is_expired')
    def test_email_verification_expired_token(self, mock_is_expired):
        """Test email verification with expired token"""
        mock_is_expired.return_value = True
        
        payload = {'token': str(self.token.token)}
        
        response = self.client.post(self.verification_url, payload)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Verification token has expired', response.data['error'])

    def test_email_verification_invalid_uuid(self):
        """Test email verification with invalid UUID format"""
        payload = {'token': 'invalid-uuid'}
        
        response = self.client.post(self.verification_url, payload)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ResendVerificationViewTest(APITestCase):
    def setUp(self):
        self.resend_url = reverse('resend-verification')  # Adjust URL name as needed
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            is_email_verified=False
        )

    @patch('your_app.views.send_verification_email_with_api')
    def test_resend_verification_success(self, mock_send_email):
        """Test successful resend of verification email"""
        mock_send_email.return_value = True
        payload = {'email': 'test@example.com'}
        
        response = self.client.post(self.resend_url, payload)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Verification email sent successfully', response.data['message'])
        mock_send_email.assert_called_once_with(self.user)

    def test_resend_verification_already_verified(self):
        """Test resend verification for already verified user"""
        self.user.is_email_verified = True
        self.user.save()
        
        payload = {'email': 'test@example.com'}
        
        response = self.client.post(self.resend_url, payload)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Email is already verified', response.data['message'])

    def test_resend_verification_nonexistent_user(self):
        """Test resend verification for non-existent user"""
        payload = {'email': 'nonexistent@example.com'}
        
        response = self.client.post(self.resend_url, payload)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('User with this email does not exist', response.data['error'])

    @patch('your_app.views.send_verification_email_with_api')
    def test_resend_verification_email_failure(self, mock_send_email):
        """Test resend verification when email sending fails"""
        mock_send_email.return_value = False
        payload = {'email': 'test@example.com'}
        
        response = self.client.post(self.resend_url, payload)
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('Failed to send verification email', response.data['error'])

    def test_resend_verification_invalid_email(self):
        """Test resend verification with invalid email format"""
        payload = {'email': 'invalid-email'}
        
        response = self.client.post(self.resend_url, payload)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CustomTokenObtainPairViewTest(APITestCase):
    def setUp(self):
        self.login_url = reverse('token_obtain_pair')  # Adjust URL name as needed
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            is_email_verified=True
        )

    def test_login_success(self):
        """Test successful login with verified email"""
        payload = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        
        response = self.client.post(self.login_url, payload)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_login_unverified_email(self):
        """Test login with unverified email"""
        self.user.is_email_verified = False
        self.user.save()
        
        payload = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        
        response = self.client.post(self.login_url, payload)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Please verify your email', str(response.data))

    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        payload = {
            'username': 'testuser',
            'password': 'wrongpassword'
        }
        
        response = self.client.post(self.login_url, payload)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ProfileViewTest(APITestCase):
    def setUp(self):
        self.profile_url = reverse('profile')  # Adjust URL name as needed
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            is_email_verified=True
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            bio='Test bio'
        )
        self.refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.refresh.access_token}')

    def test_get_profile_success(self):
        """Test successful profile retrieval"""
        response = self.client.get(self.profile_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.user.id)
        self.assertEqual(response.data['username'], 'testuser')
        self.assertEqual(response.data['email'], 'test@example.com')
        self.assertEqual(response.data['profile']['bio'], 'Test bio')

    def test_get_profile_unauthenticated(self):
        """Test profile retrieval without authentication"""
        self.client.credentials()  # Remove authentication
        
        response = self.client.get(self.profile_url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_profile_success(self):
        """Test successful profile update"""
        payload = {
            'username': 'updateduser',
            'profile': {
                'bio': 'Updated bio'
            }
        }
        
        response = self.client.patch(self.profile_url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'updateduser')
        self.assertEqual(response.data['profile']['bio'], 'Updated bio')
        
        # Verify database was updated
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.username, 'updateduser')
        self.assertEqual(self.profile.bio, 'Updated bio')

    def test_update_profile_partial(self):
        """Test partial profile update"""
        payload = {
            'profile': {
                'bio': 'New bio only'
            }
        }
        
        response = self.client.patch(self.profile_url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')  # Unchanged
        self.assertEqual(response.data['profile']['bio'], 'New bio only')


class GoogleAuthViewTest(APITestCase):
    def setUp(self):
        self.google_auth_url = reverse('google-auth')  # Adjust URL name as needed

    @patch('your_app.serializers.id_token.verify_oauth2_token')
    def test_google_auth_new_user(self, mock_verify_token):
        """Test Google authentication for new user"""
        mock_verify_token.return_value = {
            'iss': 'accounts.google.com',
            'email': 'newuser@gmail.com',
            'given_name': 'John',
            'family_name': 'Doe',
            'sub': 'google123456',
            'email_verified': True
        }
        
        payload = {'token': 'fake-google-token'}
        
        response = self.client.post(self.google_auth_url, payload)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)
        self.assertIn('refresh_token', response.data)
        self.assertEqual(response.data['user']['email'], 'newuser@gmail.com')
        self.assertEqual(response.data['user']['first_name'], 'John')
        self.assertEqual(response.data['user']['last_name'], 'Doe')
        self.assertTrue(response.data['user']['is_email_verified'])
        
        # Verify user was created
        user = User.objects.get(email='newuser@gmail.com')
        self.assertEqual(user.google_id, 'google123456')
        self.assertTrue(user.is_email_verified)

    @patch('your_app.serializers.id_token.verify_oauth2_token')
    def test_google_auth_existing_user(self, mock_verify_token):
        """Test Google authentication for existing user"""
        existing_user = User.objects.create_user(
            username='existing',
            email='existing@gmail.com',
            password='somepassword',
            first_name='Jane',
            last_name='Smith'
        )
        
        mock_verify_token.return_value = {
            'iss': 'accounts.google.com',
            'email': 'existing@gmail.com',
            'given_name': 'Jane',
            'family_name': 'Smith',
            'sub': 'google789012',
            'email_verified': True
        }
        
        payload = {'token': 'fake-google-token'}
        
        response = self.client.post(self.google_auth_url, payload)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)
        self.assertIn('refresh_token', response.data)
        self.assertEqual(response.data['user']['email'], 'existing@gmail.com')
        
        # Verify Google ID was linked
        existing_user.refresh_from_db()
        self.assertEqual(existing_user.google_id, 'google789012')
        self.assertTrue(existing_user.is_email_verified)

    @patch('your_app.serializers.id_token.verify_oauth2_token')
    def test_google_auth_existing_user_with_google_id(self, mock_verify_token):
        """Test Google authentication for user already linked to Google"""
        existing_user = User.objects.create_user(
            username='existing',
            email='existing@gmail.com',
            password='somepassword',
            google_id='google789012'
        )
        
        mock_verify_token.return_value = {
            'iss': 'accounts.google.com',
            'email': 'existing@gmail.com',
            'given_name': 'Jane',
            'family_name': 'Smith',
            'sub': 'google789012',
            'email_verified': True
        }
        
        payload = {'token': 'fake-google-token'}
        
        response = self.client.post(self.google_auth_url, payload)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)
        self.assertIn('refresh_token', response.data)

    @patch('your_app.serializers.id_token.verify_oauth2_token')
    def test_google_auth_invalid_token(self, mock_verify_token):
        """Test Google authentication with invalid token"""
        mock_verify_token.side_effect = ValueError('Invalid token')
        
        payload = {'token': 'invalid-google-token'}
        
        response = self.client.post(self.google_auth_url, payload)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid Google token', str(response.data))

    @patch('your_app.serializers.id_token.verify_oauth2_token')
    def test_google_auth_invalid_issuer(self, mock_verify_token):
        """Test Google authentication with invalid issuer"""
        mock_verify_token.return_value = {
            'iss': 'malicious.com',
            'email': 'test@gmail.com',
            'given_name': 'Test',
            'family_name': 'User',
            'sub': 'google123456',
            'email_verified': True
        }
        
        payload = {'token': 'fake-google-token'}
        
        response = self.client.post(self.google_auth_url, payload)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid token issuer', str(response.data))

    def test_google_auth_missing_token(self):
        """Test Google authentication without token"""
        payload = {}
        
        response = self.client.post(self.google_auth_url, payload)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('token', response.data)


class TokenRefreshViewTest(APITestCase):
    def setUp(self):
        self.refresh_url = reverse('token_refresh')  # Adjust URL name as needed
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            is_email_verified=True
        )
        self.refresh = RefreshToken.for_user(self.user)

    def test_token_refresh_success(self):
        """Test successful token refresh"""
        payload = {'refresh': str(self.refresh)}
        
        response = self.client.post(self.refresh_url, payload)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_token_refresh_invalid_token(self):
        """Test token refresh with invalid token"""
        payload = {'refresh': 'invalid-token'}
        
        response = self.client.post(self.refresh_url, payload)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh_missing_token(self):
        """Test token refresh without token"""
        payload = {}
        
        response = self.client.post(self.refresh_url, payload)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)