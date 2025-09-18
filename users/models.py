from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import date

class CustomUser(AbstractUser):
    """사용자 모델 - id, 아이디, 비밀번호, 이메일, 닉네임"""
    # id는 Django에서 자동 생성 (Primary Key)
    # password는 AbstractUser에서 제공 (절대 재정의하면 안됨! 자동 암호화 기능)
    
    username = models.CharField(
        max_length=150, 
        unique=True,
        verbose_name="아이디",
        help_text="로그인에 사용할 아이디 (영문, 숫자 조합)"
    )
    email = models.EmailField(
        verbose_name="이메일",
        help_text="연락용 이메일 주소"
    )
    nickname = models.CharField(
        max_length=50, 
        verbose_name="닉네임",
        help_text="화면에 표시될 이름"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="가입일")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일")
    
    # 로그인을 username(아이디)로 설정
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'nickname']  # 슈퍼유저 생성시 필수 입력
    
    def __str__(self):
        return f"{self.username} ({self.nickname})"
    
    class Meta:
        verbose_name = "사용자"
        verbose_name_plural = "사용자 목록"


class UserProfile(models.Model):
    """사용자 프로필 정보"""
    GENDER_CHOICES = [
        ('male', '남성'),
        ('female', '여성'),
        ('other', '기타'),
    ]
    
    ACTIVITY_CHOICES = [
        (1, '매우 적음 (하루 종일 앉아서 생활)'),
        (2, '적음 (가끔 산책, 계단 이용)'),  
        (3, '보통 (주 2-3회 30분 운동)'),
        (4, '많음 (주 4-5회 1시간 운동)'),
        (5, '매우 많음 (매일 고강도 운동)'),
    ]
    
    user = models.OneToOneField(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='profile',
        verbose_name="사용자"
    )
    gender = models.CharField(
        max_length=10, 
        choices=GENDER_CHOICES, 
        null=True, 
        blank=True,
        verbose_name="성별"
    )
    height_cm = models.IntegerField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(100), MaxValueValidator(250)],
        verbose_name="키 (cm)",
        help_text="100-250cm 사이로 입력해주세요"
    )
    weight_kg = models.FloatField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(30), MaxValueValidator(200)],
        verbose_name="현재 몸무게 (kg)",
        help_text="30-200kg 사이로 입력해주세요"
    )
    target_weight_kg = models.FloatField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(30), MaxValueValidator(200)],
        verbose_name="목표 체중 (kg)"
    )
    activity_level = models.IntegerField(
        choices=ACTIVITY_CHOICES,
        default=2,
        verbose_name="활동량",
        help_text="평소 운동량과 생활 패턴을 고려해주세요"
    )
    birth_date = models.DateField(
        null=True, 
        blank=True,
        verbose_name="생년월일"
    )
    phone_number = models.CharField(
        max_length=15, 
        blank=True,
        verbose_name="전화번호"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일")
    
    def __str__(self):
        return f"{self.user.email}의 프로필"
    
    @property
    def age(self):
        """나이 계산"""
        if not self.birth_date:
            return None
        today = date.today()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )
    
    @property
    def bmi(self):
        """BMI 계산"""
        if not self.height_cm or not self.weight_kg:
            return None
        height_m = self.height_cm / 100
        return round(self.weight_kg / (height_m ** 2), 1)
    
    @property
    def bmi_category(self):
        """BMI 카테고리"""
        bmi = self.bmi
        if not bmi:
            return "정보 부족"
        
        if bmi < 18.5:
            return "저체중"
        elif bmi < 25:
            return "정상"
        elif bmi < 30:
            return "과체중"
        else:
            return "비만"
    
    def get_activity_multiplier(self):
        """Harris-Benedict 공식용 활동량 계수 반환"""
        multipliers = {
            1: 1.2,    # 좌식 생활
            2: 1.375,  # 가벼운 활동  
            3: 1.55,   # 보통 활동
            4: 1.725,  # 활발한 활동
            5: 1.9     # 매우 활발
        }
        return multipliers.get(self.activity_level, 1.375)
    
    def calculate_bmr(self):
        """기초대사율 계산 (Harris-Benedict 공식)"""
        if not all([self.height_cm, self.weight_kg, self.age, self.gender]):
            return None
            
        if self.gender == 'male':
            bmr = 88.362 + (13.397 * self.weight_kg) + (4.799 * self.height_cm) - (5.677 * self.age)
        else:
            bmr = 447.593 + (9.247 * self.weight_kg) + (3.098 * self.height_cm) - (4.330 * self.age)
            
        return round(bmr, 0)
    
    def calculate_daily_calories(self):
        """일일 권장 칼로리 계산"""
        bmr = self.calculate_bmr()
        if not bmr:
            return None
        return round(bmr * self.get_activity_multiplier(), 0)
    
    class Meta:
        verbose_name = "사용자 프로필"
        verbose_name_plural = "사용자 프로필 목록"


class HealthData(models.Model):
    """일일 건강 데이터"""
    STRESS_CHOICES = [
        (1, '매우 낮음'),
        (2, '낮음'),
        (3, '보통'),
        (4, '높음'),
        (5, '매우 높음'),
    ]
    
    MOOD_CHOICES = [
        (1, '매우 나쁨'),
        (2, '나쁨'),
        (3, '보통'),
        (4, '좋음'),
        (5, '매우 좋음'),
    ]
    
    user = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE,
        related_name='health_data',
        verbose_name="사용자"
    )
    date = models.DateField(verbose_name="날짜")
    
    # 신체 측정 데이터
    weight_kg = models.FloatField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(30), MaxValueValidator(200)],
        verbose_name="오늘의 체중 (kg)"
    )
    body_fat_percentage = models.FloatField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(5), MaxValueValidator(50)],
        verbose_name="체지방률 (%)"
    )
    muscle_mass_kg = models.FloatField(
        null=True, 
        blank=True,
        verbose_name="근육량 (kg)"
    )
    
    # 생체 신호 데이터
    blood_pressure_systolic = models.IntegerField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(80), MaxValueValidator(200)],
        verbose_name="수축기 혈압 (mmHg)"
    )
    blood_pressure_diastolic = models.IntegerField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(50), MaxValueValidator(120)],
        verbose_name="이완기 혈압 (mmHg)"
    )
    heart_rate_bpm = models.IntegerField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(40), MaxValueValidator(150)],
        verbose_name="안정시 심박수 (bpm)"
    )
    
    # 수면 및 생활 패턴
    sleep_hours = models.FloatField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(24)],
        verbose_name="수면시간 (시간)"
    )
    sleep_quality = models.IntegerField(
        null=True, 
        blank=True,
        choices=[(i, f"{i}점") for i in range(1, 6)],
        verbose_name="수면 질 (1-5점)"
    )
    water_intake_ml = models.IntegerField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(5000)],
        verbose_name="물 섭취량 (ml)"
    )
    
    # 정신 건강
    stress_level = models.IntegerField(
        null=True, 
        blank=True,
        choices=STRESS_CHOICES,
        verbose_name="스트레스 수준"
    )
    mood_score = models.IntegerField(
        null=True, 
        blank=True,
        choices=MOOD_CHOICES,
        verbose_name="기분 점수"
    )
    
    # 활동량
    steps_count = models.IntegerField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(50000)],
        verbose_name="걸음 수"
    )
    exercise_minutes = models.IntegerField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(300)],
        verbose_name="운동 시간 (분)"
    )
    
    # 메모
    notes = models.TextField(
        blank=True,
        verbose_name="메모",
        help_text="오늘의 건강 상태나 특이사항을 기록해주세요"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일")
    
    def __str__(self):
        return f"{self.user.email} - {self.date}"
    
    @property
    def blood_pressure_status(self):
        """혈압 상태 판정"""
        if not self.blood_pressure_systolic or not self.blood_pressure_diastolic:
            return "측정 안함"
        
        systolic = self.blood_pressure_systolic
        diastolic = self.blood_pressure_diastolic
        
        if systolic < 120 and diastolic < 80:
            return "정상"
        elif systolic < 130 and diastolic < 80:
            return "주의"
        elif systolic < 140 or diastolic < 90:
            return "고혈압 전단계"
        else:
            return "고혈압"
    
    @property
    def weight_change(self):
        """전날 대비 체중 변화"""
        if not self.weight_kg:
            return None
            
        previous_data = HealthData.objects.filter(
            user=self.user,
            date__lt=self.date,
            weight_kg__isnull=False
        ).order_by('-date').first()
        
        if not previous_data:
            return None
            
        return round(self.weight_kg - previous_data.weight_kg, 1)
    
    class Meta:
        unique_together = ['user', 'date']  # 한 유저가 하루에 하나의 기록만
        ordering = ['-date']
        verbose_name = "건강 데이터"
        verbose_name_plural = "건강 데이터 목록"
        
# Signal을 사용해서 User 생성 시 자동으로 Profile 생성
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    """사용자 생성 시 자동으로 프로필 생성"""
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=CustomUser)
def save_user_profile(sender, instance, **kwargs):
    """사용자 저장 시 프로필도 함께 저장"""
    if hasattr(instance, 'profile'):
        instance.profile.save()        