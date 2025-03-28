from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from ckeditor.widgets import CKEditorWidget
from .models import Profile, Article, Review, Comment, Department, SiteSettings, HeroSlide, ArticleCategory

User = get_user_model()

class CustomUserCreationForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(required=True)
    department = forms.ModelChoiceField(queryset=Department.objects.all(), required=True)
    
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'department', 'password1', 'password2')
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            # Create or update profile
            department = self.cleaned_data['department']
            Profile.objects.create(user=user, department=department)
            
        return user

class CustomAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label='Email', widget=forms.EmailInput(attrs={'autofocus': True}))
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Email'

class UserRegisterForm(UserCreationForm):
    email = forms.EmailField()
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    department = forms.ModelChoiceField(queryset=Department.objects.all(), required=True)
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'password1', 'password2']
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            
            # Get the department from the form
            department = self.cleaned_data.get('department')
            
            # Check if a profile already exists for this user
            try:
                profile = Profile.objects.get(user=user)
                # Update existing profile
                profile.department = department
                profile.save()
            except Profile.DoesNotExist:
                # Create new profile if it doesn't exist
                Profile.objects.create(user=user, department=department)
                
        return user


class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField()
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name']

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['department', 'bio', 'profile_picture']

class LoginForm(AuthenticationForm):
    username = forms.EmailField(label='Email Address')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Email Address'

class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = '__all__'
        widgets = {
            'site_description': forms.Textarea(attrs={'rows': 3}),
            'footer_text': forms.Textarea(attrs={'rows': 2}),
            'primary_color': forms.TextInput(attrs={'type': 'color'}),
            'secondary_color': forms.TextInput(attrs={'type': 'color'}),
        }

class HeroSlideForm(forms.ModelForm):
    class Meta:
        model = HeroSlide
        fields = '__all__'
        widgets = {
            'subtitle': forms.Textarea(attrs={'rows': 2}),
        }

class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ['title', 'abstract', 'department', 'category', 'keywords', 'content', 'file']
        widgets = {
            'abstract': CKEditorWidget(),
            'content': CKEditorWidget(),
            'keywords': forms.TextInput(attrs={'placeholder': 'e.g., science, research, education'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Pre-select user's department if available
        if user and hasattr(user, 'profile') and user.profile.department:
            self.fields['department'].initial = user.profile.department
        
        # Set default category
        default_category = ArticleCategory.get_default()
        if default_category:
            self.fields['category'].initial = default_category

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['comments', 'decision']
        widgets = {
            'comments': forms.Textarea(attrs={'rows': 6}),
        }

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Write your comment here...'}),
        }
        labels = {
            'content': 'Comment',
        }

class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'code', 'description', 'journal_title', 'journal_description', 'cover_image']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'journal_description': forms.Textarea(attrs={'rows': 3}),
        }