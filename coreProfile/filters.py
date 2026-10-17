import django_filters

from .models import Comment, ContactMessage, Post, Project


class ProjectFilter(django_filters.FilterSet):
    tech = django_filters.CharFilter(method="filter_tech")  # ?tech=<skill-id বা নাম>

    class Meta:
        model = Project
        fields = ["category", "is_featured"]

    def filter_tech(self, queryset, name, value):
        if value.isdigit():
            return queryset.filter(tech_stack__id=value)
        return queryset.filter(tech_stack__name__iexact=value)


class PostFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(field_name="category__slug")  # ?category=<slug>
    tag = django_filters.CharFilter(field_name="tags__slug")           # ?tag=<slug>

    class Meta:
        model = Post
        fields = ["is_featured"]

# ====
class CommentFilter(django_filters.FilterSet):
    post = django_filters.CharFilter(field_name="post__slug")  # ?post=<slug>

    class Meta:
        model = Comment
        fields = ["is_approved"]  # ?is_approved=false
class ContactFilter(django_filters.FilterSet):
    class Meta:
        model = ContactMessage
        fields = ["is_read"]  # ?is_read=false