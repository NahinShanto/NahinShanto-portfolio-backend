import hashlib

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, F, Prefetch, ProtectedError, Q
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django_filters.rest_framework import DjangoFilterBackend

from .filters import CommentFilter, PostFilter, ProjectFilter
from .models import (
    Category, Comment, Education, Experience, Post, PostLike,
    Profile, Project, Skill, Tag,
)
from .pagination import CommentPagination, PostPagination, ProjectPagination
from .permissions import IsOwner, IsOwnerOrReadOnly, is_owner
from .serializers import (
    CategorySerializer, ChangePasswordSerializer, CommentAdminSerializer,
    CommentCreateSerializer, EducationSerializer, ExperienceSerializer,
    LoginSerializer, PostDetailSerializer, PostListSerializer,
    PostWriteSerializer, ProfileSerializer, ProjectSerializer,
    PublicCommentSerializer, SkillSerializer, TagSerializer, UserSerializer,
)
from .utils import get_client_ip

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

    def _visitor_id(self, request):
        return (request.headers.get("X-Visitor-Id") or "").strip()

    def retrieve(self, request, *args, **kwargs):
        post = self.get_object()
        if not is_owner(request.user):  # owner নিজের post দেখলে view বাড়বে না
            visitor = self._visitor_id(request)[:64] or get_client_ip(request) or "unknown"
            key = f"post_view:{post.slug}:{hashlib.sha1(visitor.encode()).hexdigest()}"
            # cache.add শুধু তখনই True দেয় যখন key আগে ছিল না: cooldown-এর মধ্যে একবারই গোনা হয়
            if cache.add(key, 1, timeout=settings.POST_VIEW_COOLDOWN_SECONDS):
                # F() মানে DB নিজেই "views_count + 1" করে, Python-এ পড়ে-বাড়িয়ে-লেখা নয়
                Post.objects.filter(pk=post.pk).update(views_count=F("views_count") + 1)
                post.views_count += 1  # এই response-এও নতুন সংখ্যা দেখাতে
        return Response(self.get_serializer(post).data)

    @action(detail=True, methods=["post"], url_path="like", permission_classes=[AllowAny])
    def like(self, request, slug=None):
        post = self.get_object()  # draft হলে visitor-এর জন্য 404
        visitor_id = self._visitor_id(request)
        if not visitor_id or len(visitor_id) > 64:
            return Response(
                {"detail": "A valid X-Visitor-Id header is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        like, created = PostLike.objects.get_or_create(
            post=post, visitor_id=visitor_id, defaults={"ip_address": get_client_ip(request)}
        )
        if not created:
            like.delete()  # আগেই like করা থাকলে এবার সরে যাবে (toggle)
        return Response({"liked": created, "likes_count": post.likes.count()})

    @action(detail=True, methods=["get", "post"], url_path="comments", permission_classes=[AllowAny])
    def comments(self, request, slug=None):
        post = self.get_object()
        if request.method == "POST":
            serializer = CommentCreateSerializer(data=request.data, context={"post": post})
            serializer.is_valid(raise_exception=True)
            serializer.save(post=post)  # is_approved ডিফল্টে False
            return Response(
                {"message": "Your comment is awaiting approval."},
                status=status.HTTP_201_CREATED,
            )
        approved_replies = Prefetch(
            "replies",
            queryset=Comment.objects.filter(is_approved=True).order_by("created_at"),
            to_attr="approved_replies",
        )
        qs = post.comments.filter(is_approved=True, parent__isnull=True).prefetch_related(approved_replies)
        paginator = CommentPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(PublicCommentSerializer(page, many=True).data)