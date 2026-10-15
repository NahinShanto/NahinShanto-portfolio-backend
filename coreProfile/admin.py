from django.contrib import admin
from .models import Profile, Skill, Experience, Education, Project


# Register your models here.


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "headline", "email", "is_available_for_hire")

    def has_add_permission(self, request):
        return not Profile.objects.exists()  # একটার বেশি Profile বানানো যাবে না


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "proficiency", "is_featured", "display_order")
    list_filter = ("category", "is_featured")
    search_fields = ("name",)


@admin.register(Experience)
class ExperienceAdmin(admin.ModelAdmin):
    list_display = ("role", "company", "employment_type", "start_date", "is_current")
    list_filter = ("employment_type", "is_current")
    search_fields = ("company", "role")


@admin.register(Education)
class EducationAdmin(admin.ModelAdmin):
    list_display = ("degree", "institution", "start_year", "end_year")
    search_fields = ("institution", "degree")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "is_featured", "completed_date")
    list_filter = ("category", "is_featured")
    search_fields = ("title", "summary")
    readonly_fields = ("slug",)