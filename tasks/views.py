from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet
from .models import Task
from .serializers import TaskSerializer

class TaskViewSet(ModelViewSet):
    queryset = Task.objects.all().order_by("-id")
    serializer_class = TaskSerializer