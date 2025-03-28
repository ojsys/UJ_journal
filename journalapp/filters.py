import django_filters
from .models import Article, Department, ArticleCategory

class ArticleFilter(django_filters.FilterSet):
    title = django_filters.CharFilter(lookup_expr='icontains', label='Title')
    department = django_filters.ModelChoiceFilter(
        queryset=Department.objects.all(),
        label='Department'
    )
    category = django_filters.ModelChoiceFilter(
        queryset=ArticleCategory.objects.all(),
        label='Category'
    )
    
    class Meta:
        model = Article
        fields = ['title', 'department', 'category']