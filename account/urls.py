from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView, 
    ProfileView, 
    EmailVerificationView, 
    ResendVerificationView,
    GoogleAuthView,
    login_view 
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-email/', EmailVerificationView.as_view(), name='verify-email'),
    path('resend-verification/', ResendVerificationView.as_view(), name='resend-verification'),
    path('login/', login_view, name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('auth/google/', GoogleAuthView.as_view(), name='google_auth'),
]