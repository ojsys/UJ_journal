from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from io import BytesIO
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.sites.shortcuts import get_current_site
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from .models import Article, Department, Profile, ArticleCategory, Review, SiteSettings, HeroSlide, ArchivedJournal
from .forms import (UserRegisterForm, ProfileUpdateForm, UserUpdateForm, 
                   ArticleForm, ReviewForm, CommentForm, DepartmentForm, SiteSettingsForm, HeroSlideForm)
from django_filters.views import FilterView
from .filters import ArticleFilter


def home(request):
    departments = Department.objects.all()
    latest_articles = Article.objects.filter(status='published').order_by('-published_at')[:5]
    hero_slides = HeroSlide.objects.filter(is_active=True).order_by('order')
    
    # Get featured archives
    featured_archives = ArchivedJournal.objects.filter(featured=True).order_by('-publication_date')[:3]
    
    context = {
        'departments': departments,
        'latest_articles': latest_articles,
        'hero_slides': hero_slides,
    }
    
    return render(request, 'journalapp/home.html', context)


################ Authentication Views #######################
def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Send welcome email
            send_welcome_email(request, user)
            messages.success(request, f'Your account has been created! You can now log in.')
            return redirect('login')
    else:
        form = UserRegisterForm()
    
    context = {
        'form': form,
        'departments': Department.objects.all()
    }
    return render(request, 'journalapp/register.html', context)


def send_welcome_email(request, user):
    current_site = get_current_site(request)
    site_url = f"{'https' if request.is_secure() else 'http'}://{current_site.domain}"
    
    context = {
        'user': user,
        'site_url': site_url,
    }
    
    # Render email templates
    html_content = render_to_string('journalapp/emails/welcome_email.html', context)
    text_content = render_to_string('journalapp/emails/welcome_email.txt', context)
    
    # Create email
    subject = "Welcome to University Journal"
    from_email = "University Journal <noreply@universityjournal.com>"
    to_email = user.email
    
    # Send email
    email = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
    email.attach_alternative(html_content, "text/html")
    
    try:
        email.send()
    except Exception as e:
        # Log the error but don't prevent user registration
        print(f"Error sending welcome email: {e}")




def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        remember = request.POST.get('remember')
        
        # Try to authenticate with email directly
        user = authenticate(request, email=email, password=password)
        
        # If that fails, try with username parameter (Django's default)
        if user is None:
            user = authenticate(request, username=email, password=password)
        
        if user is not None:
            login(request, user)
            # Get the next parameter or default to dashboard
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url:
                return redirect(next_url)
            else:
                return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'journalapp/login.html')


def logout_view(request):
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect('home')

@login_required
def profile(request):
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.profile)
        
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, f'Your profile has been updated!')
            return redirect('profile')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)
    
    context = {
        'u_form': u_form,
        'p_form': p_form
    }
    return render(request, 'journalapp/profile.html', context)


################ End of Authentication Views #######################

@login_required
def dashboard(request):
    # Get all user articles
    user_articles = Article.objects.filter(author=request.user).order_by('-created_at')
    
    # Count articles by status
    published_count = user_articles.filter(status='published').count()
    under_review_count = user_articles.filter(status__in=['submitted', 'under_review']).count()
    draft_count = user_articles.filter(status='draft').count()
    revision_required_count = user_articles.filter(status='revision_required').count()
    
    # For editors and reviewers
    if request.user.profile.is_editor:
        pending_articles = Article.objects.filter(status='submitted').order_by('-created_at')
    else:
        pending_articles = None
        
    if request.user.profile.is_reviewer:
        review_articles = Article.objects.filter(status='under_review').order_by('-created_at')
    else:
        review_articles = None
    
    context = {
        'user_articles': user_articles,
        'pending_articles': pending_articles,
        'review_articles': review_articles,
        'published_count': published_count,
        'under_review_count': under_review_count,
        'draft_count': draft_count,
        'revision_required_count': revision_required_count,
        'total_count': len(user_articles),
    }
    return render(request, 'journalapp/dashboard.html', context)


@login_required
def upload_revised_document(request, pk):
    article = get_object_or_404(Article, pk=pk)
    
    # Check if user is editor or admin
    if not request.user.profile.is_editor and not request.user.is_staff:
        messages.error(request, 'You do not have permission to upload revised documents.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        if 'revised_document' in request.FILES:
            article.revised_document = request.FILES['revised_document']
            article.revision_notes = request.POST.get('revision_notes', '')
            article.status = 'revision_required'  # Update status
            article.save()
            
            # Notify the author
            send_revision_notification(request, article)
            
            messages.success(request, 'Revised document uploaded successfully.')
        else:
            messages.error(request, 'No document was uploaded.')
    
    return redirect('dashboard')


def send_revision_notification(request, article):
    current_site = get_current_site(request)
    site_url = f"{'https' if request.is_secure() else 'http'}://{current_site.domain}"
    dashboard_url = f"{site_url}/dashboard/"
    
    context = {
        'article': article,
        'user': article.author,
        'site_url': site_url,
        'dashboard_url': dashboard_url,
        'revision_notes': article.revision_notes,
    }
    
    # Render email templates
    html_content = render_to_string('journalapp/emails/revision_notification.html', context)
    text_content = strip_tags(html_content)
    
    # Create email
    subject = f"Revision Required: {article.title}"
    from_email = "University Journal <noreply@universityjournal.com>"
    to_email = article.author.email
    
    # Send email
    email = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
    email.attach_alternative(html_content, "text/html")
    
    try:
        email.send()
        print(f"Revision notification email sent to {to_email}")
    except Exception as e:
        print(f"Error sending revision notification email: {e}")




def department_journal(request, department_id):
    department = get_object_or_404(Department, id=department_id)
    published_articles = Article.objects.filter(
        department=department,
        status='published'
    ).order_by('-published_at')
    
    context = {
        'department': department,
        'articles': published_articles,
    }
    return render(request, 'journalapp/department_journal.html', context)


class ArticleListView(FilterView):
    model = Article
    template_name = 'journalapp/article_list.html'
    context_object_name = 'articles'
    filterset_class = ArticleFilter
    paginate_by = 10
    
    def get_queryset(self):
        return Article.objects.filter(status='published').order_by('-published_at')

class ArticleDetailView(DetailView):
    model = Article
    template_name = 'journalapp/article_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comment_form'] = CommentForm()
        return context

class ArticleCreateView(LoginRequiredMixin, CreateView):
    model = Article
    form_class = ArticleForm
    template_name = 'journalapp/article_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        messages.success(self.request, 'Article created successfully!')
        return reverse_lazy('dashboard')

class ArticleUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Article
    form_class = ArticleForm
    template_name = 'journalapp/article_form.html'
    success_url = reverse_lazy('dashboard')
    
    def form_valid(self, form):
        messages.success(self.request, 'Article updated successfully!')
        return super().form_valid(form)
    
    def test_func(self):
        article = self.get_object()
        return self.request.user == article.author

class ArticleDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Article
    template_name = 'journalapp/article_confirm_delete.html'
    success_url = reverse_lazy('dashboard')
    
    def test_func(self):
        article = self.get_object()
        return self.request.user == article.author

@login_required
def submit_article(request, pk):
    article = get_object_or_404(Article, pk=pk, author=request.user)
    if article.status == 'draft':
        article.status = 'submitted'
        article.save()
        messages.success(request, 'Article submitted successfully!')
    return redirect('dashboard')

@login_required
def review_article(request, pk):
    article = get_object_or_404(Article, pk=pk)
    if not request.user.profile.is_reviewer:
        messages.error(request, 'You do not have permission to review journals.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.article = article
            review.reviewer = request.user
            review.save()
            
            # Update journal status based on review decision
            decision = form.cleaned_data.get('decision')
            if decision == 'accept':
                article.status = 'accepted'
            elif decision in ['minor_revision', 'major_revision']:
                article.status = 'revision_required'
                # Store revision notes from the review
                article.revision_notes = review.comments
                # Send notification to the author
                send_revision_notification(request, article)
            elif decision == 'reject':
                article.status = 'rejected'
            article.save()
            
            messages.success(request, 'Review submitted successfully!')
            return redirect('dashboard')
    else:
        form = ReviewForm()
    
    context = {
        'form': form,
        'article': article
    }
    return render(request, 'journalapp/review_form.html', context)

    

@login_required
def publish_article(request, pk):
    article = get_object_or_404(Article, pk=pk)
    if not request.user.profile.is_editor:
        messages.error(request, 'You do not have permission to publish articles.')
        return redirect('dashboard')
    
    if article.status == 'accepted':
        article.publish()
        messages.success(request, 'Article published successfully!')
    return redirect('dashboard')


############## HERO SLIDER #############
@staff_member_required
def site_settings(request):
    settings, created = SiteSettings.objects.get_or_create(pk=1)
    
    if request.method == 'POST':
        form = SiteSettingsForm(request.POST, request.FILES, instance=settings)
        if form.is_valid():
            form.save()
            messages.success(request, 'Site settings updated successfully!')
            return redirect('site_settings')
    else:
        form = SiteSettingsForm(instance=settings)
    
    context = {
        'form': form,
        'title': 'Site Settings'
    }
    return render(request, 'journalapp/site_settings.html', context)

@staff_member_required
def hero_slides(request):
    slides = HeroSlide.objects.all().order_by('order')
    
    context = {
        'slides': slides,
        'title': 'Hero Slides'
    }
    return render(request, 'journalapp/hero_slides.html', context)

@staff_member_required
def hero_slide_create(request):
    if request.method == 'POST':
        form = HeroSlideForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Hero slide created successfully!')
            return redirect('hero_slides')
    else:
        form = HeroSlideForm()
    
    context = {
        'form': form,
        'title': 'Create Hero Slide'
    }
    return render(request, 'journalapp/hero_slide_form.html', context)

@staff_member_required
def hero_slide_update(request, pk):
    slide = get_object_or_404(HeroSlide, pk=pk)
    
    if request.method == 'POST':
        form = HeroSlideForm(request.POST, request.FILES, instance=slide)
        if form.is_valid():
            form.save()
            messages.success(request, 'Hero slide updated successfully!')
            return redirect('hero_slides')
    else:
        form = HeroSlideForm(instance=slide)
    
    context = {
        'form': form,
        'title': 'Update Hero Slide'
    }
    return render(request, 'journalapp/hero_slide_form.html', context)

@staff_member_required
def hero_slide_delete(request, pk):
    slide = get_object_or_404(HeroSlide, pk=pk)
    
    if request.method == 'POST':
        slide.delete()
        messages.success(request, 'Hero slide deleted successfully!')
        return redirect('hero_slides')
    
    context = {
        'slide': slide,
        'title': 'Delete Hero Slide'
    }
    return render(request, 'journalapp/hero_slide_confirm_delete.html', context)



class AllJournalsListView(ListView):
    model = Article
    template_name = 'journalapp/all_journals.html'
    context_object_name = 'journals'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = Article.objects.filter(status='published')
        
        # Filter by department
        department_id = self.request.GET.get('department')
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        
        # Search functionality
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                models.Q(title__icontains=search_query) |
                models.Q(abstract__icontains=search_query) |
                models.Q(content__icontains=search_query)
            )
        
        # Sorting
        sort_by = self.request.GET.get('sort', 'newest')
        if sort_by == 'newest':
            queryset = queryset.order_by('-published_at')
        elif sort_by == 'oldest':
            queryset = queryset.order_by('published_at')
        elif sort_by == 'title':
            queryset = queryset.order_by('title')
        else:
            queryset = queryset.order_by('-published_at')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['departments'] = Department.objects.all()
        return context


class JournalListView(ListView):
    model = Department
    template_name = 'journalapp/journal_list.html'
    context_object_name = 'journals'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # For each department, get the count of published articles
        for journal in context['journals']:
            journal.article_count = Article.objects.filter(
                department=journal,
                status='published'
            ).count()
        return context


############# PDF Export ###############
def article_pdf(request, pk):
    article = get_object_or_404(Article, pk=pk)
    template = get_template('journalapp/article_pdf.html')
    context = {
        'article': article,
        'request': request,
    }
    html = template.render(context)
    
    # Create a PDF
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        filename = f"{article.title.replace(' ', '_')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    
    return HttpResponse("Error generating PDF", status=400)

class ArticleSearchView(ListView):
    model = Article
    template_name = 'journalapp/article_search.html'
    context_object_name = 'articles'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = Article.objects.filter(status='published')
        
        # Search functionality
        search_query = self.request.GET.get('q', '')
        if search_query:
            queryset = queryset.filter(
                models.Q(title__icontains=search_query) |
                models.Q(abstract__icontains=search_query) |
                models.Q(content__icontains=search_query) |
                models.Q(author__first_name__icontains=search_query) |
                models.Q(author__last_name__icontains=search_query) |
                models.Q(keywords__icontains=search_query)
            )
        
        # Filter by department
        department_id = self.request.GET.get('department')
        if department_id:
            queryset = queryset.filter(department_id=department_id)
            
        # Filter by category
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(categories__id=category_id)
        
        # Sorting
        sort_by = self.request.GET.get('sort', 'newest')
        if sort_by == 'newest':
            queryset = queryset.order_by('-published_at')
        elif sort_by == 'oldest':
            queryset = queryset.order_by('published_at')
        elif sort_by == 'title':
            queryset = queryset.order_by('title')
        elif sort_by == 'author':
            queryset = queryset.order_by('author__last_name', 'author__first_name')
        else:
            queryset = queryset.order_by('-published_at')
        
        return queryset.distinct()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['departments'] = Department.objects.all()
        context['categories'] = ArticleCategory.objects.all()
        context['search_query'] = self.request.GET.get('q', '')
        context['selected_department'] = self.request.GET.get('department', '')
        context['selected_category'] = self.request.GET.get('category', '')
        context['selected_sort'] = self.request.GET.get('sort', 'newest')
        return context

# Add these views for archived journals

@staff_member_required
def archived_journals_list(request):
    archives = ArchivedJournal.objects.all().order_by('-publication_date')
    
    # Filter by department
    department_id = request.GET.get('department')
    if department_id:
        archives = archives.filter(department_id=department_id)
    
    # Search functionality
    search_query = request.GET.get('q')
    if search_query:
        archives = archives.filter(
            models.Q(title__icontains=search_query) |
            models.Q(description__icontains=search_query) |
            models.Q(volume__icontains=search_query) |
            models.Q(issue__icontains=search_query)
        )
    
    context = {
        'archives': archives,
        'departments': Department.objects.all(),
        'title': 'Archived Journals',
        'search_query': search_query,
        'selected_department': department_id,
    }
    return render(request, 'journalapp/archived_journals_list.html', context)

@staff_member_required
def archived_journal_create(request):
    if request.method == 'POST':
        form = ArchivedJournalForm(request.POST, request.FILES)
        if form.is_valid():
            archived_journal = form.save(commit=False)
            archived_journal.uploaded_by = request.user
            archived_journal.save()
            messages.success(request, 'Archived journal uploaded successfully!')
            return redirect('archived_journals_list')
    else:
        form = ArchivedJournalForm()
    
    context = {
        'form': form,
        'title': 'Upload Archived Journal'
    }
    return render(request, 'journalapp/archived_journal_form.html', context)

@staff_member_required
def archived_journal_update(request, pk):
    archived_journal = get_object_or_404(ArchivedJournal, pk=pk)
    
    if request.method == 'POST':
        form = ArchivedJournalForm(request.POST, request.FILES, instance=archived_journal)
        if form.is_valid():
            form.save()
            messages.success(request, 'Archived journal updated successfully!')
            return redirect('archived_journals_list')
    else:
        form = ArchivedJournalForm(instance=archived_journal)
    
    context = {
        'form': form,
        'archived_journal': archived_journal,
        'title': 'Update Archived Journal'
    }
    return render(request, 'journalapp/archived_journal_form.html', context)

@staff_member_required
def archived_journal_delete(request, pk):
    archived_journal = get_object_or_404(ArchivedJournal, pk=pk)
    
    if request.method == 'POST':
        archived_journal.delete()
        messages.success(request, 'Archived journal deleted successfully!')
        return redirect('archived_journals_list')
    
    context = {
        'archived_journal': archived_journal,
        'title': 'Delete Archived Journal'
    }
    return render(request, 'journalapp/archived_journal_confirm_delete.html', context)

# Public view for archived journals
def public_archived_journals(request):
    archives = ArchivedJournal.objects.all().order_by('-publication_date')
    
    # Filter by department
    department_id = request.GET.get('department')
    if department_id:
        archives = archives.filter(department_id=department_id)
        selected_department = Department.objects.get(id=department_id)
    else:
        selected_department = None
    
    # Search functionality
    search_query = request.GET.get('q')
    if search_query:
        archives = archives.filter(
            models.Q(title__icontains=search_query) |
            models.Q(description__icontains=search_query) |
            models.Q(volume__icontains=search_query) |
            models.Q(issue__icontains=search_query)
        )
    
    context = {
        'archives': archives,
        'departments': Department.objects.all(),
        'search_query': search_query,
        'selected_department': selected_department,
    }
    return render(request, 'journalapp/public_archived_journals.html', context)

def archived_journal_detail(request, pk):
    archived_journal = get_object_or_404(ArchivedJournal, pk=pk)
    
    context = {
        'archived_journal': archived_journal,
    }
    return render(request, 'journalapp/archived_journal_detail.html', context)