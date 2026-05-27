from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Organisation

admin.site.register(Organisation)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Breathe ESG', {'fields': ('organisation', 'role')}),
    )
