from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views
import ipaddress


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")
    try:
        ipaddress.ip_address(ip)
    except (ValueError, TypeError):
        return None
    return ip  

router = DefaultRouter()
router.register("skills", views.SkillViewSet, basename="skill")
router.register("experiences", views.ExperienceViewSet, basename="experience")
router.register("education", views.EducationViewSet, basename="education")
router.register("projects", views.ProjectViewSet, basename="project")
router.register("categories", views.CategoryViewSet, basename="category")
router.register("tags", views.TagViewSet, basename="tag")
router.register("posts", views.PostViewSet, basename="post")
router.register("contact", views.ContactViewSet, basename="contact")


urlpatterns = [
    path("auth/login/", views.LoginView.as_view(), name="auth-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("auth/logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", views.MeView.as_view(), name="auth-me"),
    path("auth/change-password/", views.ChangePasswordView.as_view(), name="auth-change-password"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("", include(router.urls)),
    path("dashboard/stats/", views.DashboardStatsView.as_view(), name="dashboard-stats"),
]