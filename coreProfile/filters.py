import django_filters

from .models import Project


class ProjectFilter(django_filters.FilterSet):
    tech = django_filters.CharFilter(method="filter_tech")  # ?tech=<skill-id বা নাম>

    class Meta:
        model = Project
        fields = ["category", "is_featured"]

    def filter_tech(self, queryset, name, value):
        if value.isdigit():
            return queryset.filter(tech_stack__id=value)
        return queryset.filter(tech_stack__name__iexact=value)