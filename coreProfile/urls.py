from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views


router = DefaultRouter()
router.register("skills", views.SkillViewSet, basename="skill")
router.register("experiences", views.ExperienceViewSet, basename="experience")
router.register("education", views.EducationViewSet, basename="education")



urlpatterns = [
    path("auth/login/", views.LoginView.as_view(), name="auth-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("auth/logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", views.MeView.as_view(), name="auth-me"),
    path("auth/change-password/", views.ChangePasswordView.as_view(), name="auth-change-password"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("", include(router.urls)),
]