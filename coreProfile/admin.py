from django.contrib import admin
from .models import (
    Profile, Skill, Experience, Education, Project,
    Category, Tag, Post, PostLike, Comment, ContactMessage,
)


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



@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    readonly_fields = ("slug",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    readonly_fields = ("slug",)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "category", "views_count", "published_at", "is_featured")
    list_filter = ("status", "category", "is_featured")
    search_fields = ("title", "excerpt", "content")
    filter_horizontal = ("tags",)
    exclude = ("author",)
    readonly_fields = ("slug", "published_at", "reading_time", "views_count")

    def save_model(self, request, obj, form, change):
        if not obj.author_id:
            obj.author = request.user  # author সবসময় লগইন করা owner
        super().save_model(request, obj, form, change)


@admin.register(PostLike)
class PostLikeAdmin(admin.ModelAdmin):
    list_display = ("post", "visitor_id", "ip_address", "created_at")
    search_fields = ("visitor_id", "post__title")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("name", "post", "is_approved", "parent", "created_at")
    list_filter = ("is_approved",)
    search_fields = ("name", "email", "content")


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "name", "email", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("name", "email", "subject")