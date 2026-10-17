import hashlib
from datetime import datetime

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, F, Prefetch, ProtectedError, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .filters import CommentFilter, ContactFilter, PostFilter, ProjectFilter
from .models import (
    Category, Comment, ContactMessage, Education, Experience, Post,
    PostLike, Profile, Project, Skill, Tag,
)
from .pagination import CommentPagination, ContactPagination, PostPagination, ProjectPagination
from .permissions import IsOwner, IsOwnerOrReadOnly, is_owner
from .serializers import (
    CategorySerializer, ChangePasswordSerializer, CommentAdminSerializer,
    CommentCreateSerializer, ContactAdminSerializer, ContactCreateSerializer,
    EducationSerializer, ExperienceSerializer, LoginSerializer,
    PostDetailSerializer, PostListSerializer, PostWriteSerializer,
    ProfileSerializer, ProjectSerializer, PublicCommentSerializer,
    SkillSerializer, TagSerializer, UserSerializer,
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

    def get_throttles(self):
        if self.action == "like":
            self.throttle_scope = "like"
        elif self.action == "comments" and self.request.method == "POST":
            self.throttle_scope = "comment"  # শুধু comment পাঠানোয় limit, পড়ায় নয়
        else:
            self.throttle_scope = None
        return super().get_throttles()
    
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


# ==========

class ContactViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = ContactMessage.objects.all()
    pagination_class = ContactPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = ContactFilter
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action == "create":
            return [AllowAny()]  # visitor পাঠাতে পারবে
        return [IsOwner()]       # পড়া, মার্ক, মোছা শুধু owner

    def get_serializer_class(self):
        return ContactCreateSerializer if self.action == "create" else ContactAdminSerializer

    def get_throttles(self):
        self.throttle_scope = "contact" if self.action == "create" else None
        return super().get_throttles()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Thank you! Your message has been sent."}, status=status.HTTP_201_CREATED)


class DashboardStatsView(APIView):
    permission_classes = [IsOwner]

    def get(self, request):
        published = Post.Status.PUBLISHED
        # প্রতিটাই DB-তে একটা aggregate query, Python loop নয়
        post_stats = Post.objects.aggregate(
            total_posts=Count("id"),
            published_posts=Count("id", filter=Q(status=published)),
            draft_posts=Count("id", filter=Q(status=Post.Status.DRAFT)),
            total_views=Coalesce(Sum("views_count"), 0),
        )
        comment_stats = Comment.objects.aggregate(
            total_comments=Count("id"),
            pending_comments=Count("id", filter=Q(is_approved=False)),
        )
        top_posts = (
            Post.objects.filter(status=published)
            .annotate(likes_total=Count("likes"))
            .order_by("-views_count")[:5]
        )
        recent_comments = Comment.objects.select_related("post")[:5]

        # শেষ ৬ মাস (এই মাস সহ), যে মাসে post নেই সেখানে 0
        today = timezone.localdate()
        months, y, m = [], today.year, today.month
        for _ in range(6):
            months.append((y, m))
            m -= 1
            if m == 0:
                y, m = y - 1, 12
        months.reverse()
        since = timezone.make_aware(datetime(months[0][0], months[0][1], 1))
        per_month = (
            Post.objects.filter(created_at__gte=since)
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )
        counts = {(r["month"].year, r["month"].month): r["count"] for r in per_month}

        return Response({
            **post_stats,
            **comment_stats,
            "total_projects": Project.objects.count(),
            "total_skills": Skill.objects.count(),
            "total_likes": PostLike.objects.count(),
            "unread_messages": ContactMessage.objects.filter(is_read=False).count(),
            "top_posts": [
                {"title": p.title, "slug": p.slug, "views": p.views_count, "likes": p.likes_total}
                for p in top_posts
            ],
            "recent_comments": CommentAdminSerializer(recent_comments, many=True).data,
            "posts_per_month": [
                {
                    "month": f"{yy}-{mm:02d}",
                    "label": datetime(yy, mm, 1).strftime("%b %Y"),
                    "count": counts.get((yy, mm), 0),
                }
                for yy, mm in months
            ],
        })