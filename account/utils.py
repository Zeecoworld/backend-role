from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import requests
from .models import EmailVerificationToken


def send_verification_email_with_api(user):
    """Send verification email using Mailtrap API"""
    
    # Debug configuration
    print(f"🔍 API Token: {settings.MAILTRAP_API_TOKEN[:10]}..." if settings.MAILTRAP_API_TOKEN else "❌ No token")
    print(f"🔍 Inbox ID: {settings.MAILTRAP_INBOX_ID}")
    print(f"🔍 From Email: {settings.DEFAULT_FROM_EMAIL}")
    
    # Create or get existing token
    token, created = EmailVerificationToken.objects.get_or_create(
        user=user,
        is_used=False,
        defaults={'user': user}
    )
    
    if not created and token.is_expired():
        token.delete()
        token = EmailVerificationToken.objects.create(user=user)
    
    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token.token}"
    
    try:
        html_message = render_to_string('emails/verification_email.html', {
            'user': user,
            'verification_url': verification_url,
            'token': token.token
        })
        print("✓ Template loaded successfully")
    except Exception as e:
        print(f"✗ Template loading failed: {e}")
        return False
    
    plain_message = strip_tags(html_message)
    
    # Correct Mailtrap API endpoint
    url = f"https://sandbox.api.mailtrap.io/api/send/{settings.MAILTRAP_INBOX_ID}"
    
    payload = {
        "from": {
            "email": settings.DEFAULT_FROM_EMAIL,
            "name": "Your App"
        },
        "to": [
            {
                "email": "engrisaac1234@gmail.com",  # Use actual user email
                "name": user.username
            }
        ],
        "subject": "Verify Your Email Address",
        "text": plain_message,
        "html": html_message,
        "category": "Email Verification"
    }
    
    headers = {
        "Authorization": f"Bearer {settings.MAILTRAP_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        print(f"🔄 Request URL: {url}")
        print(f"📊 Status Code: {response.status_code}")
        print(f"📝 Response: {response.text}")
        
        if response.status_code == 200:
            print("✓ Email sent successfully via Mailtrap API")
            return True
        else:
            print(f"✗ Email sending failed: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ API request failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False
