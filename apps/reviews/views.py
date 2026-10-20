from rest_framework import permissions, viewsets

from .models import Review
from .serializers import ReviewSerializer
from .services import has_purchased


class IsAuthorOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user_id == request.user.id or request.user.is_staff


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly)
    filterset_fields = ("product", "rating", "is_verified_purchase")
    ordering_fields = ("created_at", "rating")
    ordering = ("-created_at",)

    def get_queryset(self):
        return Review.objects.filter(is_approved=True).select_related("user", "product")

    def perform_create(self, serializer):
        product = serializer.validated_data["product"]
        serializer.save(
            user=self.request.user,
            is_verified_purchase=has_purchased(self.request.user, product),
        )
