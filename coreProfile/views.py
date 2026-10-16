from django.db.models import Count, ProtectedError, Q
from rest_framework import filters, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django_filters.rest_framework import DjangoFilterBackend

from .filters import PostFilter, ProjectFilter
from .models import Category, Education, Experience, Post, Profile, Project, Skill, Tag
from .pagination import PostPagination, ProjectPagination
from .permissions import IsOwner, IsOwnerOrReadOnly, is_owner
from .serializers import (
    CategorySerializer, ChangePasswordSerializer, EducationSerializer,
    ExperienceSerializer, LoginSerializer, PostDetailSerializer,
    PostListSerializer, PostWriteSerializer, ProfileSerializer,
    ProjectSerializer, SkillSerializer, TagSerializer, UserSerializer,
)
# Create your views here.

class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer


class LogoutView(APIView):
    permission_classes = [IsOwner]

    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response({"detail": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            RefreshToken(refresh).blacklist()
        except TokenError:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsOwner]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    permission_classes = [IsOwner]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()
        return Response({"detail": "Password changed successfully."})


# =============================================================
class ProfileView(APIView):
    """Singleton: GET সবার জন্য, PATCH শুধু owner।"""
    permission_classes = [IsOwnerOrReadOnly]

    def get(self, request):
        profile = Profile.get_solo()
        if profile is None:
            return Response({"detail": "Profile has not been set up yet."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProfileSerializer(profile, context={"request": request}).data)

    def patch(self, request):
        profile = Profile.get_solo()
        if profile is None:
            serializer = ProfileSerializer(data=request.data, context={"request": request})
        else:
            serializer = ProfileSerializer(
                profile, data=request.data, partial=True, context={"request": request}
            )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class SkillViewSet(viewsets.ModelViewSet):
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
    permission_classes = [IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["category", "is_featured"]
    search_fields = ["name"]
    ordering_fields = ["display_order", "proficiency"]


class ExperienceViewSet(viewsets.ModelViewSet):
    queryset = Experience.objects.all()
    serializer_class = ExperienceSerializer
    permission_classes = [IsOwnerOrReadOnly]


class EducationViewSet(viewsets.ModelViewSet):
    queryset = Education.objects.all()
    serializer_class = EducationSerializer
    permission_classes = [IsOwnerOrReadOnly]


# ----------------------------------
class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.prefetch_related("tech_stack")
    serializer_class = ProjectSerializer
    permission_classes = [IsOwnerOrReadOnly]
    lookup_field = "slug"  
    pagination_class = ProjectPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProjectFilter
    search_fields = ["title", "summary", "description"]
    ordering_fields = ["completed_date", "display_order"]

# ========================
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.annotate(
        published_count=Count("posts", filter=Q(posts__status=Post.Status.PUBLISHED))
    )
    serializer_class = CategorySerializer
    permission_classes = [IsOwnerOrReadOnly]

    def destroy(self, request, *args, **kwargs):
        category = self.get_object()
        try:
            category.delete()
        except ProtectedError:
            used = category.posts.count()
            return Response(
                {"detail": f"This category is used by {used} post(s) and cannot be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.annotate(
        published_count=Count("posts", filter=Q(posts__status=Post.Status.PUBLISHED))
    )
    serializer_class = TagSerializer
    permission_classes = [IsOwnerOrReadOnly]


class PostViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOwnerOrReadOnly]
    lookup_field = "slug"
    pagination_class = PostPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = PostFilter
    search_fields = ["title", "excerpt", "content"]
    ordering_fields = ["published_at", "views_count", "likes_count", "title"]

    def get_queryset(self):
        qs = (
            Post.objects.select_related("category", "author")
            .prefetch_related("tags")
            .annotate(
                likes_count=Count("likes", distinct=True),
                comments_count=Count("comments", filter=Q(comments__is_approved=True), distinct=True),
            )
        )
        if is_owner(self.request.user):
            if self.action == "list":
                wanted = (self.request.query_params.get("status") or "").upper()
                if wanted == "ALL":
                    return qs
                if wanted in (Post.Status.DRAFT, Post.Status.PUBLISHED):
                    return qs.filter(status=wanted)
                return qs.filter(status=Post.Status.PUBLISHED)
            return qs  # owner detail/edit/delete-এ draft-ও পায়
        return qs.filter(status=Post.Status.PUBLISHED)  # visitor শুধু published দেখে (draft → 404)

    def get_serializer_class(self):
        if self.action == "list":
            return PostListSerializer
        if self.action == "retrieve":
            return PostDetailSerializer
        return PostWriteSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)  # author সবসময় owner