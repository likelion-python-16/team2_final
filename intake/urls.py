from rest_framework.routers import SimpleRouter
from .views import FoodViewSet, MealViewSet, NutritionLogViewSet  

router = SimpleRouter()
router.register("foods", FoodViewSet)
router.register("meals", MealViewSet)
router.register("nutrition-logs", NutritionLogViewSet)
urlpatterns = router.urls