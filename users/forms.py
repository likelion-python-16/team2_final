# users/forms.py
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from .models import CustomUser  # 프로젝트에서 CustomUser를 실제로 쓰고 있다면 유지

User = get_user_model()


# -------------------------------
# 최초 설정 폼 (setup_view에서 사용)
# -------------------------------
class SetupForm(forms.Form):
    GOAL_CHOICES = [
        ("lose_weight", "Lose Weight"),
        ("gain_muscle", "Gain Muscle"),
        ("maintain", "Maintain"),
        ("endurance", "Endurance"),
    ]
    # 표시용 텍스트에 설명을 포함해두었지만, 실제 값은 왼쪽 키만 DB에 저장됩니다.
    ACTIVITY_CHOICES = [
        ("sedentary", "Sedentary | Little to no exercise"),
        ("light", "Light | Light exercise 1-3 days/week"),
        ("moderate", "Moderate | Moderate exercise 3-5 days/week"),
        ("very_active", "Very Active | Hard exercise 6-7 days/week"),
    ]

    name = forms.CharField(label="Full Name", max_length=100)
    age = forms.IntegerField(label="Age", min_value=10, max_value=120)
    weight = forms.FloatField(label="Weight (kg)", min_value=20, max_value=500)
    height = forms.IntegerField(label="Height (cm)", min_value=100, max_value=250)
    goal = forms.ChoiceField(
        label="Fitness Goal", choices=GOAL_CHOICES, initial="maintain"
    )
    activity_level = forms.ChoiceField(
        label="Activity Level", choices=ACTIVITY_CHOICES, initial="moderate"
    )


# -------------------------------
# 회원가입 폼
# - UserCreationForm 상속으로 password1/password2 자동 포함
# - email: 선택 입력, 중복 검사
# - nickname: 선택 입력(미입력 시 username으로 대체 저장)
# -------------------------------
class SignUpForm(UserCreationForm):
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(
            attrs={"placeholder": "Email", "autocomplete": "email"}
        ),
        help_text="선택 입력 (중복 불가)",
        label="Email",
    )
    nickname = forms.CharField(
        required=False,
        max_length=50,
        widget=forms.TextInput(attrs={"placeholder": "Nickname"}),
        help_text="선택 입력",
        label="Nickname",
    )

    class Meta(UserCreationForm.Meta):
        # 실제로 사용하는 User 모델을 따라감(CustomUser 또는 기본 User)
        model = User
        # UserCreationForm는 password1/password2를 자동으로 추가하므로 여기에는 계정 기본 필드만 나열
        fields = ("username", "email", "nickname")

        widgets = {
            "username": forms.TextInput(
                attrs={"placeholder": "Username", "autocomplete": "username"}
            ),
        }
        labels = {
            "username": "Username",
        }
        help_texts = {
            "username": "",
        }

    # --------- 폼 초기화: 공통 스타일/순서 ---------
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 공통 클래스 적용 + 불필요 help_text 제거
        field_order = ["username", "nickname", "email", "password1", "password2"]
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", "auth-input")
            # 기본 help_text 제거(템플릿이 깔끔해짐)
            field.help_text = ""

        # password 필드 placeholder/자동완성
        if "password1" in self.fields:
            self.fields["password1"].widget.attrs.setdefault("placeholder", "Password")
            self.fields["password1"].widget.attrs.setdefault(
                "autocomplete", "new-password"
            )
        if "password2" in self.fields:
            self.fields["password2"].widget.attrs.setdefault(
                "placeholder", "Confirm Password"
            )
            self.fields["password2"].widget.attrs.setdefault(
                "autocomplete", "new-password"
            )

        self.order_fields(field_order)

    # --------- 검증 ---------
    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        if email:
            # 이메일을 유니크로 운영하고 싶으면 중복 검사
            if User.objects.filter(email__iexact=email).exists():
                raise ValidationError("이미 사용 중인 이메일입니다.")
        return email

    # (선택) username 사전 중복 검사(모델에서 unique면 DB 레벨에서도 잡힘)
    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise ValidationError("아이디를 입력하세요.")
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("이미 사용 중인 아이디입니다.")
        return username

    # --------- 저장 ---------
    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data.get("email") or ""
        nickname = self.cleaned_data.get("nickname") or ""

        # 필드 존재 시 저장
        if hasattr(user, "email"):
            user.email = email
        if hasattr(user, "nickname"):
            user.nickname = nickname or user.username

        if commit:
            user.save()
        return user
