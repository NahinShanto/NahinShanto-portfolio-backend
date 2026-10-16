from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from datetime import date
from .models import Education, Experience, Profile, Project, Skill
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