from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.urls import reverse
from django.shortcuts import render
from rest_framework import permissions, viewsets

from .models import Exercise, TaskItem, WorkoutLog, WorkoutPlan
from .serializers import (
    ExerciseSerializer,
    TaskItemSerializer,
    WorkoutLogSerializer,
    WorkoutPlanSerializer,
)

class ExerciseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Exercise.objects.all()
    serializer_class = ExerciseSerializer
    permission_classes = [permissions.IsAuthenticated]

class WorkoutPlanViewSet(viewsets.ModelViewSet):
    queryset = WorkoutPlan.objects.all()
    serializer_class = WorkoutPlanSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WorkoutPlan.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class TaskItemViewSet(viewsets.ModelViewSet):
    queryset = TaskItem.objects.all()
    serializer_class = TaskItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return TaskItem.objects.filter(workout_plan__user=self.request.user)

class WorkoutLogViewSet(viewsets.ModelViewSet):
    queryset = WorkoutLog.objects.all()
    serializer_class = WorkoutLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WorkoutLog.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@login_required
def dashboard(request):
    """템플릿 대시보드"""

    summary = {
        "total_minutes": (
            WorkoutLog.objects.filter(user=request.user)
            .aggregate(Sum("duration_min"))["duration_min__sum"]
            or 0
        ),
        "recommended_intensity": "Medium",
        "active_plans": WorkoutPlan.objects.filter(user=request.user).count(),
    }
    recommendations = (
        TaskItem.objects.filter(workout_plan__user=request.user)
        .select_related("exercise")
        .order_by("order")[:4]
    )

    daily_tasks = [
        {
            "id": item.id,
            "text": f"{item.exercise.name} {item.duration_min} min",
            "completed": False,
            "type": "workout",
        }
        for item in recommendations
    ]
    if not daily_tasks:
        daily_tasks = [
            {"id": "water", "text": "Drink 8 glasses of water", "completed": False, "type": "water"},
            {"id": "sleep", "text": "Get 7+ hours sleep", "completed": True, "type": "sleep"},
            {"id": "meal", "text": "Log breakfast calories", "completed": True, "type": "meal"},
        ]

    completed_count = sum(1 for task in daily_tasks if task["completed"])
    total_tasks = len(daily_tasks)
    progress_complete = int(round(completed_count / total_tasks * 100)) if total_tasks else 0

    ai_insights = [
        {
            "id": "progress",
            "type": "success",
            "title": "Great Progress!",
            "message": "Your nutrition tracking stayed above 90% of target this week.",
            "confidence": 94,
        },
        {
            "id": "tip",
            "type": "info",
            "title": "Optimization Tip",
            "message": "Add 15 minutes of light cardio after strength sessions for better fat burn.",
            "confidence": 87,
        },
    ]

    progress_cards = [
        {"label": "Calories", "value": "1,847", "render_value": "1,847", "render_percent": 75, "progress": 75, "color": "primary"},
        {"label": "Workouts", "value": "3/5", "render_value": "3/5", "render_percent": 60, "progress": 60, "color": "secondary"},
        {"label": "Sleep", "value": "6.2h", "render_value": "6.2h", "render_percent": 40, "progress": 40, "color": "coral"},
    ]

    quick_actions = [
        {
            "icon": "zap",
            "title": "Start Workout",
            "caption": "Begin today's training",
            "url": reverse("tasks_workouts"),
            "variant": "primary",
        },
        {
            "icon": "camera",
            "title": "Log Meal",
            "caption": "Take a photo",
            "url": reverse("tasks_meals"),
            "variant": "secondary",
        },
        {
            "icon": "trend",
            "title": "View Progress",
            "caption": "Check your stats",
            "url": "#progress",
            "variant": "coral",
        },
        {
            "icon": "target",
            "title": "Set Goals",
            "caption": "Update targets",
            "url": "#goal",
            "variant": "purple",
        },
    ]

    return render(
        request,
        "tasks/dashboard.html",
        {
            "summary": summary,
            "recommendations": recommendations,
            "daily_tasks": daily_tasks,
            "ai_insights": ai_insights,
            "progress_cards": progress_cards,
            "quick_actions": quick_actions,
            "ai_loading": False,
            "progress_complete": progress_complete,
            "progress_total": total_tasks,
            "progress_done": completed_count,
        },
    )


@login_required
def workouts(request):
    week_days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    workouts_plan = [
        {
            'id': '1',
            'name': 'Upper Body Strength',
            'type': 'strength',
            'duration': 45,
            'difficulty': 'intermediate',
            'completed': True,
            'exercises': [
                {'id': '1', 'name': 'Push-ups', 'sets': 3, 'reps': 12},
                {'id': '2', 'name': 'Pull-ups', 'sets': 3, 'reps': 8},
                {'id': '3', 'name': 'Dumbbell Press', 'sets': 3, 'reps': 10},
            ],
        },
        {
            'id': '2',
            'name': 'HIIT Cardio',
            'type': 'hiit',
            'duration': 30,
            'difficulty': 'advanced',
            'completed': False,
            'exercises': [
                {'id': '1', 'name': 'Burpees', 'duration': 30},
                {'id': '2', 'name': 'Mountain Climbers', 'duration': 30},
                {'id': '3', 'name': 'Jump Squats', 'duration': 30},
            ],
        },
        {
            'id': '3',
            'name': 'Lower Body Power',
            'type': 'strength',
            'duration': 50,
            'difficulty': 'intermediate',
            'completed': False,
            'exercises': [
                {'id': '1', 'name': 'Squats', 'sets': 4, 'reps': 15},
                {'id': '2', 'name': 'Lunges', 'sets': 3, 'reps': 12},
                {'id': '3', 'name': 'Deadlifts', 'sets': 3, 'reps': 10},
            ],
        },
    ]
    return render(
        request,
        'tasks/workouts.html',
        {
            'week_days': week_days,
            'workouts_plan': workouts_plan,
        },
    )


@login_required
def meals(request):
    nutrition_goals = {
        "calories": 2200,
        "protein": 150,
        "carbs": 220,
        "fat": 80,
    }

    todays_meals = [
        {
            "id": "1",
            "name": "Protein Overnight Oats",
            "type": "breakfast",
            "calories": 420,
            "protein": 25,
            "carbs": 45,
            "fat": 12,
            "image": "https://images.unsplash.com/photo-1571091718767-18b5b1457add?w=400&h=300&fit=crop",
            "ai_generated": True,
        },
        {
            "id": "2",
            "name": "Grilled Chicken Quinoa Bowl",
            "type": "lunch",
            "calories": 550,
            "protein": 45,
            "carbs": 40,
            "fat": 18,
            "image": "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=400&h=300&fit=crop",
            "ai_generated": True,
        },
    ]

    type_meta = {
        "breakfast": {"label": "Breakfast", "badge": "meal-badge meal-badge--breakfast"},
        "lunch": {"label": "Lunch", "badge": "meal-badge meal-badge--lunch"},
        "dinner": {"label": "Dinner", "badge": "meal-badge meal-badge--dinner"},
        "snack": {"label": "Snack", "badge": "meal-badge meal-badge--snack"},
    }

    for meal in todays_meals:
        meta = type_meta.get(meal["type"], {"label": meal["type"].title(), "badge": "meal-badge"})
        meal["type_label"] = meta["label"]
        meal["badge_class"] = meta["badge"]

    consumed_nutrition = {
        "calories": sum(meal["calories"] for meal in todays_meals),
        "protein": sum(meal["protein"] for meal in todays_meals),
        "carbs": sum(meal["carbs"] for meal in todays_meals),
        "fat": sum(meal["fat"] for meal in todays_meals),
    }

    nutrition_summary = [
        {
            "label": "Calories",
            "current": consumed_nutrition["calories"],
            "goal": nutrition_goals["calories"],
            "color": "primary",
            "unit": "cal",
            "progress": min(int(round(consumed_nutrition["calories"] / nutrition_goals["calories"] * 100)) if nutrition_goals["calories"] else 0, 100),
        },
        {
            "label": "Protein",
            "current": consumed_nutrition["protein"],
            "goal": nutrition_goals["protein"],
            "color": "success",
            "unit": "g",
            "progress": min(int(round(consumed_nutrition["protein"] / nutrition_goals["protein"] * 100)) if nutrition_goals["protein"] else 0, 100),
        },
        {
            "label": "Carbs",
            "current": consumed_nutrition["carbs"],
            "goal": nutrition_goals["carbs"],
            "color": "warning",
            "unit": "g",
            "progress": min(int(round(consumed_nutrition["carbs"] / nutrition_goals["carbs"] * 100)) if nutrition_goals["carbs"] else 0, 100),
        },
        {
            "label": "Fat",
            "current": consumed_nutrition["fat"],
            "goal": nutrition_goals["fat"],
            "color": "secondary",
            "unit": "g",
            "progress": min(int(round(consumed_nutrition["fat"] / nutrition_goals["fat"] * 100)) if nutrition_goals["fat"] else 0, 100),
        },
    ]

    ai_feedback_cards = [
        {
            "type": "suggestion",
            "message": "You're 300 calories below your goal. Consider adding a protein-rich snack to reach your targets.",
        }
    ]

    ai_recommendations = [
        {
            "title": "🥗 Dinner Suggestion",
            "message": "Based on your remaining calories and macros, try a salmon and sweet potato dish.",
            "button": "View Recipe",
        },
        {
            "type": "achievement",
            "message": "Great protein intake today! You're 90% towards your protein goal.",
        },
    ]

    return render(
        request,
        "tasks/meals.html",
        {
            "nutrition_summary": nutrition_summary,
            "todays_meals": todays_meals,
            "nutrition_goals": nutrition_goals,
            "ai_feedback_cards": ai_feedback_cards,
            "ai_recommendations": ai_recommendations,
        },
    )
