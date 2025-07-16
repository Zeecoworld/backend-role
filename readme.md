# 5thSocial Django Backend

## Setup Instructions

1. Create a virtual environment:
   ```
   python -m venv env
   source env/bin/activate  # or env\Scripts\activate on Windows
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run migrations:
   ```
   python manage.py migrate
   ```

4. Run the development server:
   ```
   python manage.py runserver
   ```

Default auth uses JWT and includes `/api/account/` and `/api/posts/` APIs.