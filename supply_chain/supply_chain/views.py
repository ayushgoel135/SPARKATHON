from django.shortcuts import redirect

def home_view(request):
    # Redirect to either inventory or admin dashboard
    return redirect('inventory_dashboard')  # or 'admin:index' for admin panel