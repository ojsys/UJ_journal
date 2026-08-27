import django_filters
from .models import Article, ArticleCategory, Journal


class ArticleFilter(django_filters.FilterSet):
    title = django_filters.CharFilter(lookup_expr='icontains', label='Title')
    # Filter by journal rather than department: a department can run several
    # journals, so "Department of English" was never a useful narrowing.
    journal = django_filters.ModelChoiceFilter(
        queryset=Journal.objects.filter(is_active=True),
        label='Journal',
        to_field_name='slug',
    )
    category = django_filters.ModelChoiceFilter(
        queryset=ArticleCategory.objects.all(),
        label='Category'
    )

    class Meta:
        model = Article
        fields = ['title', 'journal', 'category']
