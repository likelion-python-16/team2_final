from django.contrib import admin
from .models import CustomUser,HealthData,UserProfile

# Register your models here.
admin.site.register(CustomUser)
admin.site.register(HealthData)
admin.site.register(UserProfile)