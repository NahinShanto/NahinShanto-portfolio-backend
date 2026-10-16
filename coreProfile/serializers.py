from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from datetime import date
from .models import Category, Education, Experience, Post, Profile, Project, Skill, Tag
from .validators import validate_image, validate_pdf


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email")


class LoginSerializer(TokenObtainPairSerializer):
    """access + refresh token-এর সাথে user তথ্যও ফেরত দেয়।"""

    def validate(self, attrs):
        data = super().validate(attrs)  # ভুল password হলে এখানেই 401 error ওঠে
        data["user"] = UserSerializer(self.user).data
        return data


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def validate_new_password(self, value):
        validate_password(value, self.context["request"].user)
        return value


# ------------------------------------------------

class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = "__all__"

    def validate_avatar(self, value):
        return validate_image(value) if value else value

    def validate_resume(self, value):
        return validate_pdf(value) if value else value


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = "__all__"

    def validate_proficiency(self, value):
        if not 1 <= value <= 100:
            raise serializers.ValidationError("Proficiency must be between 1 and 100.")
        return value

    def validate_icon(self, value):
        return validate_image(value) if value else value


class ExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experience
        fields = "__all__"

    def validate_start_date(self, value):
        if value > date.today():
            raise serializers.ValidationError("Start date cannot be in the future.")
        return value

    def validate(self, attrs):
        def get(field):
            return attrs.get(field, getattr(self.instance, field, None))

        start, end, current = get("start_date"), get("end_date"), get("is_current")

        if current:
            if end:
                raise serializers.ValidationError(
                    {"end_date": "End date must be empty for a current position."}
                )
        else:
            if not end:
                raise serializers.ValidationError(
                    {"end_date": "End date is required unless this is your current position."}
                )
            if start and end <= start:
                raise serializers.ValidationError(
                    {"end_date": "End date must be after start date."}
                )
        return attrs


class EducationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Education
        fields = "__all__"

    def validate(self, attrs):
        start = attrs.get("start_year", getattr(self.instance, "start_year", None))
        end = attrs.get("end_year", getattr(self.instance, "end_year", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_year": "End year cannot be before start year."}
            )
        return attrs

# -------------------------------------------

class SkillMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ("id", "name", "category")


class ProjectSerializer(serializers.ModelSerializer):
    tech_stack = SkillMiniSerializer(many=True, read_only=True)
    tech_stack_ids = serializers.PrimaryKeyRelatedField(
        queryset=Skill.objects.all(),
        many=True,
        write_only=True,
        source="tech_stack",
        required=False,
    )

    class Meta:
        model = Project
        fields = (
            "id", "title", "slug", "summary", "description", "cover_image",
            "tech_stack", "tech_stack_ids", "category", "live_url", "github_url",
            "is_featured", "completed_date", "display_order",
            "created_at", "updated_at",
        )
        read_only_fields = ("slug",)

    def validate_cover_image(self, value):
        return validate_image(value) if value else value

    def validate(self, attrs):
        live = attrs.get("live_url", getattr(self.instance, "live_url", ""))
        github = attrs.get("github_url", getattr(self.instance, "github_url", ""))
        if not live and not github:
            msg = "Provide at least one of live URL or GitHub URL."
            raise serializers.ValidationError({"live_url": msg, "github_url": msg})
        return attrs

# ===============================================
class CategoryMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug")


class TagMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("id", "name", "slug")


class CategorySerializer(serializers.ModelSerializer):
    posts_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "description", "posts_count")
        read_only_fields = ("slug",)

    def get_posts_count(self, obj):
        # শুধু PUBLISHED post গোনা হয়
        count = getattr(obj, "published_count", None)
        if count is None:
            count = obj.posts.filter(status=Post.Status.PUBLISHED).count()
        return count


class TagSerializer(serializers.ModelSerializer):
    posts_count = serializers.SerializerMethodField()

    class Meta:
        model = Tag
        fields = ("id", "name", "slug", "posts_count")
        read_only_fields = ("slug",)

    def get_posts_count(self, obj):
        count = getattr(obj, "published_count", None)
        if count is None:
            count = obj.posts.filter(status=Post.Status.PUBLISHED).count()
        return count


class PostListSerializer(serializers.ModelSerializer):
    category = CategoryMiniSerializer(read_only=True)
    tags = TagMiniSerializer(many=True, read_only=True)
    likes_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "id", "title", "slug", "excerpt", "cover_image", "category", "tags",
            "status", "published_at", "views_count", "reading_time", "is_featured",
            "likes_count", "comments_count", "created_at",
        )

    def get_likes_count(self, obj):
        # queryset-এ annotate করা থাকলে সেটাই নেয়, না থাকলে (create/update-এর পর) গুনে নেয়
        value = getattr(obj, "likes_count", None)
        return value if value is not None else obj.likes.count()

    def get_comments_count(self, obj):
        value = getattr(obj, "comments_count", None)
        if value is None:
            value = obj.comments.filter(is_approved=True).count()
        return value


class PostDetailSerializer(PostListSerializer):
    author = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    related_posts = serializers.SerializerMethodField()

    class Meta(PostListSerializer.Meta):
        fields = PostListSerializer.Meta.fields + (
            "content", "updated_at", "author", "is_liked", "related_posts",
        )

    def get_author(self, obj):
        return obj.author.get_full_name() or obj.author.username

    def get_is_liked(self, obj):
        request = self.context.get("request")
        visitor_id = request.headers.get("X-Visitor-Id") if request else None
        if not visitor_id:
            return False
        return obj.likes.filter(visitor_id=visitor_id).exists()

    def get_related_posts(self, obj):
        if not obj.category_id:
            return []
        related = (
            Post.objects.filter(status=Post.Status.PUBLISHED, category_id=obj.category_id)
            .exclude(pk=obj.pk)
            .select_related("category")
            .prefetch_related("tags")[:3]
        )
        return PostListSerializer(related, many=True, context=self.context).data


class PostWriteSerializer(serializers.ModelSerializer):
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source="category", required=False, allow_null=True
    )
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, source="tags", required=False
    )

    class Meta:
        model = Post
        fields = (
            "title", "excerpt", "content", "cover_image",
            "category_id", "tag_ids", "status", "is_featured",
        )

    def validate_title(self, value):
        value = value.strip()
        if len(value) < 5:
            raise serializers.ValidationError("Title must be at least 5 characters long.")
        return value

    def validate_cover_image(self, value):
        return validate_image(value) if value else value

    def validate(self, attrs):
        def get(field):
            if field in attrs:
                return attrs[field]
            return getattr(self.instance, field, None)

        status = get("status") or Post.Status.DRAFT
        if status == Post.Status.PUBLISHED:
            errors = {}
            if len((get("content") or "").strip()) < 100:
                errors["content"] = "A published post must have at least 100 characters of content."
            if not get("category"):
                errors["category_id"] = "A published post must have a category."
            if errors:
                raise serializers.ValidationError(errors)
        return attrs

    def to_representation(self, instance):
        # লেখার পর response-এ পুরো detail ফেরত যায়
        return PostDetailSerializer(instance, context=self.context).data