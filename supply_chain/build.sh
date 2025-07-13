#!/usr/bin/env bash
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Apply database migrations
python manage.py migrate

# Create superuser non-interactively only if it doesn't exist
echo "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.create_superuser('$Ayush13579', '$gppg317@gmail.com', '$1234567890') if not User.objects.filter(username='$Ayush13579').exists() else None" | python manage.py shell
