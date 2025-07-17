from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import requests
from .models import EmailVerificationToken


def send_verification_email_with_api(user):

    
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
    except Exception as e:
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
        
        if response.status_code == 200:
            return True
        else:
            return False
            
    except requests.exceptions.RequestException as e:
        return False
    except Exception as e:
        return False
