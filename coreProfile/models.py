from django.db import models
from django.utils.text import slugify
# Create your models here.


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True  

class Profile(TimeStampedModel):
    full_name = models.CharField(max_length=100)
    headline = models.CharField(max_length=150)
    bio = models.TextField()
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    location = models.CharField(max_length=100, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    resume = models.FileField(upload_to="resumes/", blank=True, null=True)
    github_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    x_url = models.URLField(blank=True)
    website_url = models.URLField(blank=True)
    years_of_experience = models.PositiveIntegerField(default=0)
    is_available_for_hire = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        self.pk = 1 
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        return cls.objects.filter(pk=1).first()

    def __str__(self):
        return self.full_name


class Skill(TimeStampedModel):
    class Category(models.TextChoices):
        FRONTEND = "FRONTEND", "Frontend"
        BACKEND = "BACKEND", "Backend"
        DATABASE = "DATABASE", "Database"
        DEVOPS = "DEVOPS", "DevOps"
        TOOLS = "TOOLS", "Tools"
        SOFT_SKILL = "SOFT_SKILL", "Soft Skill"

    name = models.CharField(max_length=60, unique=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    proficiency = models.PositiveIntegerField(default=50) 
    icon = models.ImageField(upload_to="skill_icons/", blank=True, null=True)
    display_order = models.IntegerField(default=0)
    is_featured = models.BooleanField(default=False)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class Experience(TimeStampedModel):
    class EmploymentType(models.TextChoices):
        FULL_TIME = "FULL_TIME", "Full-time"
        PART_TIME = "PART_TIME", "Part-time"
        INTERNSHIP = "INTERNSHIP", "Internship"
        FREELANCE = "FREELANCE", "Freelance"
        CONTRACT = "CONTRACT", "Contract"

    company = models.CharField(max_length=120)
    role = models.CharField(max_length=120)
    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices)
    location = models.CharField(max_length=100, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    company_url = models.URLField(blank=True)
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.role} @ {self.company}"


class Education(TimeStampedModel):
    institution = models.CharField(max_length=150)
    degree = models.CharField(max_length=120)
    field_of_study = models.CharField(max_length=120)
    start_year = models.PositiveIntegerField()
    end_year = models.PositiveIntegerField(null=True, blank=True)
    grade = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_year"]
        verbose_name_plural = "education"

    def __str__(self):
        return f"{self.degree} - {self.institution}"


class Project(TimeStampedModel):
    class Category(models.TextChoices):
        WEB = "WEB", "Web"
        MOBILE = "MOBILE", "Mobile"
        API = "API", "API"
        ML = "ML", "Machine Learning"
        OTHER = "OTHER", "Other"

    title = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=170, unique=True, blank=True, editable=False)
    summary = models.CharField(max_length=200)
    description = models.TextField()
    cover_image = models.ImageField(upload_to="projects/")
    tech_stack = models.ManyToManyField(Skill, related_name="projects", blank=True)
    category = models.CharField(max_length=10, choices=Category.choices, default=Category.WEB)
    live_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    is_featured = models.BooleanField(default=False)
    completed_date = models.DateField(null=True, blank=True)
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["display_order", "-completed_date"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)
            slug, n = base, 2
            while Project.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
