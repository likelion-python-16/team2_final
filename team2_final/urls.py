from django.contrib import admin
from django.urls import path,include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
        
    path('users/', include('users.urls')),
    path('tasks/', include('tasks.urls')),
    path('goals/', include('goals.urls')),
    path('intake/', include('intake.urls')),    
    path('feedbacks/', include('feedbacks.urls')),  
    
]
