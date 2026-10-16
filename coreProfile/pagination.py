from rest_framework.pagination import PageNumberPagination


class ProjectPagination(PageNumberPagination):
    page_size = 9

class PostPagination(PageNumberPagination):
    page_size = 6