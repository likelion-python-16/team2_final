from django.contrib import admin
from .models import User, Goal, Task, Food, Intake, Feedback

admin.site.register(User)
admin.site.register(Goal)
admin.site.register(Task)
admin.site.register(Food)
admin.site.register(Intake)
admin.site.register(Feedback)