from django import forms


class SetupForm(forms.Form):
    GOAL_CHOICES = [
        ("lose_weight", "Lose Weight"),
        ("gain_muscle", "Gain Muscle"),
        ("maintain", "Maintain"),
        ("endurance", "Endurance"),
    ]

    ACTIVITY_CHOICES = [
        ("sedentary", "Sedentary|Little to no exercise"),
        ("light", "Light|Light exercise 1-3 days/week"),
        ("moderate", "Moderate|Moderate exercise 3-5 days/week"),
        ("very_active", "Very Active|Hard exercise 6-7 days/week"),
    ]

    name = forms.CharField(label="Full Name", max_length=100)
    age = forms.IntegerField(label="Age", min_value=10, max_value=100)
    weight = forms.FloatField(label="Weight (kg)", min_value=30, max_value=200)
    height = forms.IntegerField(label="Height (cm)", min_value=130, max_value=230)
    goal = forms.ChoiceField(label="Fitness Goal", choices=GOAL_CHOICES, initial="maintain")
    activity_level = forms.ChoiceField(label="Activity Level", choices=ACTIVITY_CHOICES, initial="moderate")
