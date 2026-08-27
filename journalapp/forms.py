from django import forms
from django.db import models
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from ckeditor.widgets import CKEditorWidget
from .models import (
    Profile, Article, Review, Comment, Department, SiteSettings,
    HeroSlide, ArticleCategory, Journal, Issue, EditorialBoardMember, JournalPage,
    Submission, Assignment, SubmissionMessage, DocumentVersion,
    GuestReviewer, JournalRole, Rubric, ChecklistItem, ReviewerApplication,
    JournalFee
)

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
    document_upload = forms.FileField(
        label="Upload Your Manuscript",
        required=False,
        help_text="Upload a .docx or .pdf file to automatically populate the form fields below."
    )

    class Meta:
        model = Article
        fields = ['title', 'abstract', 'journal', 'category', 'keywords', 'content', 'document_upload']
        widgets = {
            'abstract': CKEditorWidget(),
            'content': CKEditorWidget(),
            'keywords': forms.TextInput(attrs={'placeholder': 'e.g., science, research, education'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = ArticleCategory.objects.none()

        if 'journal' in self.data:
            try:
                journal_id = int(self.data.get('journal'))
                self.fields['category'].queryset = ArticleCategory.objects.filter(journal_id=journal_id).order_by('name')
            except (ValueError, TypeError):
                pass  # invalid input from the client; ignore and fallback to empty queryset
        elif self.instance.pk and self.instance.journal:
            self.fields['category'].queryset = self.instance.journal.categories.order_by('name')

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
        fields = ['name', 'code', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

class JournalForm(forms.ModelForm):
    """Full journal record, for site administrators."""
    class Meta:
        model = Journal
        fields = ['name', 'slug', 'abbreviation', 'tagline', 'description', 'about',
                  'logo', 'cover_image', 'issn_print', 'issn_online', 'published_by',
                  'contact_email', 'department', 'order', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'about': CKEditorWidget(),
        }

class AssignReviewerForm(forms.Form):
    reviewer = forms.ModelChoiceField(
        queryset=User.objects.filter(profile__is_reviewer=True),
        label="Select a Reviewer",
        widget=forms.Select(attrs={'class': 'form-control'})
    )



################### Submission Workflow Forms #########################

class SubmissionForm(forms.ModelForm):
    """Form for authors to submit their articles"""
    class Meta:
        model = Submission
        fields = ['journal', 'document', 'cover_letter']
        widgets = {
            'cover_letter': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Optional: Include a cover letter or notes for the editor...'
            }),
            'document': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.doc,.docx'
            }),
        }
        labels = {
            'journal': 'Select Journal',
            'document': 'Upload Manuscript (Word Document)',
            'cover_letter': 'Cover Letter (Optional)',
        }
        help_texts = {
            'document': 'Please upload your article in Microsoft Word format (.doc or .docx)',
        }

    def clean_document(self):
        document = self.cleaned_data.get('document')
        if document:
            # Check file extension
            ext = document.name.split('.')[-1].lower()
            if ext not in ['doc', 'docx']:
                raise forms.ValidationError('Only Word documents (.doc, .docx) are allowed.')
            # Check file size (max 10MB)
            if document.size > 10 * 1024 * 1024:
                raise forms.ValidationError('File size must be under 10MB.')
        return document


class SubmissionEditForm(forms.ModelForm):
    """Let an author correct their submission and optionally replace the file.

    The document is optional here: an author fixing a typo in the title or cover
    letter shouldn't be forced to re-upload. When a file *is* supplied it becomes
    a new DocumentVersion (handled in the view), so nothing is overwritten.
    """
    new_document = forms.FileField(
        required=False,
        label='Replace manuscript (optional)',
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.doc,.docx'}),
        help_text='Leave empty to keep your current file. Uploading here adds a new version.',
    )

    class Meta:
        model = Submission
        fields = ['title', 'cover_letter']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'cover_letter': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 5,
                'placeholder': 'Optional cover letter or notes for the editor...',
            }),
        }

    def clean_new_document(self):
        document = self.cleaned_data.get('new_document')
        if document:
            ext = document.name.split('.')[-1].lower()
            if ext not in ['doc', 'docx']:
                raise forms.ValidationError('Only Word documents (.doc, .docx) are allowed.')
            if document.size > 10 * 1024 * 1024:
                raise forms.ValidationError('File size must be under 10MB.')
        return document


class SubmissionAssignmentForm(forms.ModelForm):
    """Form for admin to assign reviewers or editors to submissions"""
    class Meta:
        model = Assignment
        fields = ['assigned_to', 'role', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional notes for the assignee...'
            }),
        }

    def __init__(self, *args, role=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Set default role if provided
        if role:
            self.fields['role'].initial = role
            if role == 'reviewer':
                self.fields['assigned_to'].queryset = User.objects.filter(
                    profile__is_reviewer=True
                ).select_related('profile')
                self.fields['assigned_to'].label = 'Select Reviewer'
            elif role == 'editor':
                self.fields['assigned_to'].queryset = User.objects.filter(
                    profile__is_editor=True
                ).select_related('profile')
                self.fields['assigned_to'].label = 'Select Editor'
        else:
            # Show all eligible users
            self.fields['assigned_to'].queryset = User.objects.filter(
                models.Q(profile__is_reviewer=True) | models.Q(profile__is_editor=True)
            ).select_related('profile').distinct()

        self.fields['assigned_to'].widget.attrs['class'] = 'form-control'
        self.fields['assigned_to'].empty_label = '-- Select a user --'
        self.fields['role'].widget.attrs['class'] = 'form-control'
        self.fields['role'].empty_label = '-- Select role --'


class AssignmentFeedbackForm(forms.ModelForm):
    """Form for reviewers/editors to submit their feedback"""
    class Meta:
        model = Assignment
        fields = ['feedback', 'recommendation', 'amended_document']
        widgets = {
            'feedback': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Provide your detailed feedback on the submission...'
            }),
            'recommendation': forms.Select(attrs={'class': 'form-control'}),
            'amended_document': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.doc,.docx,.pdf'
            }),
        }
        labels = {
            'feedback': 'Your Feedback',
            'recommendation': 'Your Recommendation',
            'amended_document': 'Upload Amended Document (Optional)',
        }
        help_texts = {
            'amended_document': 'Upload the document with your annotations, corrections, or suggested changes',
        }


class SubmissionMessageForm(forms.ModelForm):
    """Form for sending chat messages"""
    class Meta:
        model = SubmissionMessage
        fields = ['content', 'attachment']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Type your message...'
            }),
            'attachment': forms.FileInput(attrs={
                'class': 'form-control'
            }),
        }
        labels = {
            'content': '',
            'attachment': 'Attach File (Optional)',
        }


class DocumentVersionForm(forms.ModelForm):
    """Form for uploading new document versions"""
    class Meta:
        model = DocumentVersion
        fields = ['document', 'notes', 'is_final']
        widgets = {
            'document': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.doc,.docx'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Notes about this version...'
            }),
        }
        labels = {
            'document': 'Upload Document',
            'is_final': 'Mark as Final Version',
        }


class ReviewCopyUploadForm(forms.Form):
    """Chief Editor uploads a de-identified copy for reviewers to download."""
    document = forms.FileField(
        label='Review-ready manuscript',
        help_text='Upload a de-identified copy (author name and affiliation '
                  'removed). This is what reviewers will download.',
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.doc,.docx'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 'rows': 2,
            'placeholder': 'Optional note about this review copy...',
        })
    )

    def clean_document(self):
        document = self.cleaned_data.get('document')
        if document:
            ext = document.name.split('.')[-1].lower()
            if ext not in ['doc', 'docx']:
                raise forms.ValidationError('Only Word documents (.doc, .docx) are allowed.')
            if document.size > 10 * 1024 * 1024:
                raise forms.ValidationError('File size must be under 10MB.')
        return document


class FinalDocumentUploadForm(forms.Form):
    """Form for admin to upload the final approved document"""
    document = forms.FileField(
        label='Final Approved Document',
        help_text='Upload the final approved Word document for content extraction',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.doc,.docx'
        })
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional notes about this final version...'
        })
    )

    def clean_document(self):
        document = self.cleaned_data.get('document')
        if document:
            ext = document.name.split('.')[-1].lower()
            if ext not in ['doc', 'docx']:
                raise forms.ValidationError('Only Word documents (.doc, .docx) are allowed.')
        return document


class PublishArticleForm(forms.ModelForm):
    """Form for admin to add publication metadata before publishing"""
    class Meta:
        model = Article
        fields = ['title', 'abstract', 'keywords', 'content', 'category',
                  'issue', 'page_start', 'page_end', 'doi',
                  'extracted_citations']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'abstract': CKEditorWidget(),
            'keywords': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., science, research, education'
            }),
            'content': CKEditorWidget(),
            'issue': forms.Select(attrs={'class': 'form-select'}),
            'page_start': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 45'
            }),
            'page_end': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 62'
            }),
            'doi': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 10.1234/journal.2024.001'
            }),
            'extracted_citations': CKEditorWidget(),
        }
        labels = {
            'extracted_citations': 'References/Citations',
            'page_start': 'Start Page',
            'page_end': 'End Page',
            'issue': 'Publish in issue',
        }
        help_texts = {
            'issue': 'Only issues belonging to this journal are listed. '
                     'Create one first under Manage journal \u2192 Issues.',
        }

    def __init__(self, *args, journal=None, **kwargs):
        # The issue list must never offer another journal's editions, so scope it
        # to the journal being published into. The article doesn't exist yet at
        # this point, so the journal is passed in by the view; an unscoped form
        # offers nothing rather than every issue on the site.
        super().__init__(*args, **kwargs)
        journal = journal or getattr(self.instance, 'journal', None)
        self.fields['issue'].queryset = (
            Issue.objects.filter(journal=journal) if journal else Issue.objects.none()
        )
        self.fields['issue'].required = False
        self.fields['issue'].empty_label = '— not assigned to an issue —'


class RevisionRequestForm(forms.Form):
    """Form for admin to request revisions from author"""
    notes = forms.CharField(
        label='Revision Notes',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Describe what revisions are needed...'
        }),
        help_text='These notes will be sent to the author via email.'
    )


################### Guest Reviewer Forms #########################

class GuestReviewerForm(forms.ModelForm):
    """Form for adding a single guest reviewer"""
    class Meta:
        model = GuestReviewer
        fields = ['email', 'first_name', 'last_name', 'affiliation', 'expertise_areas']
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'reviewer@example.com'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First Name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last Name'
            }),
            'affiliation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Institution or Organization'
            }),
            'expertise_areas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'e.g., Machine Learning, Data Science, NLP (comma-separated)'
            }),
        }
        help_texts = {
            'email': 'Guest reviewer will receive invitation emails at this address.',
            'expertise_areas': 'Enter areas of expertise separated by commas.',
        }

    def clean_email(self):
        """Validate that email is not already in use"""
        email = self.cleaned_data.get('email')
        if email:
            # Check if email exists in GuestReviewer
            if GuestReviewer.objects.filter(email=email).exists():
                if not self.instance.pk:  # Only check on creation, not update
                    raise forms.ValidationError('A guest reviewer with this email already exists.')
            # Check if email exists in CustomUser
            from .models import CustomUser
            if CustomUser.objects.filter(email=email).exists():
                raise forms.ValidationError('This email is already registered as a user account.')
        return email


class BulkGuestReviewerForm(forms.Form):
    """Form for adding multiple guest reviewers at once"""
    reviewer_list = forms.CharField(
        label='Reviewer List',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 10,
            'placeholder': 'Enter one reviewer per line in the format:\nemail@example.com, First Name, Last Name, Affiliation\n\nExample:\njohn@example.com, John, Doe, MIT\njane@example.com, Jane, Smith, Harvard'
        }),
        help_text='Enter one reviewer per line. Format: email, first name, last name, affiliation (optional)'
    )

    def clean_reviewer_list(self):
        """Parse and validate the reviewer list"""
        reviewer_list = self.cleaned_data.get('reviewer_list', '').strip()
        if not reviewer_list:
            raise forms.ValidationError('Please provide at least one reviewer.')

        lines = [line.strip() for line in reviewer_list.split('\n') if line.strip()]
        parsed_reviewers = []
        errors = []

        for i, line in enumerate(lines, 1):
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 3:
                errors.append(f'Line {i}: Invalid format. Need at least email, first name, and last name.')
                continue

            email = parts[0]
            first_name = parts[1]
            last_name = parts[2]
            affiliation = parts[3] if len(parts) > 3 else ''

            # Validate email format
            try:
                forms.EmailField().clean(email)
            except forms.ValidationError:
                errors.append(f'Line {i}: Invalid email address "{email}".')
                continue

            # Check if email already exists
            if GuestReviewer.objects.filter(email=email).exists():
                errors.append(f'Line {i}: Email "{email}" already exists as a guest reviewer.')
                continue

            from .models import CustomUser
            if CustomUser.objects.filter(email=email).exists():
                errors.append(f'Line {i}: Email "{email}" is already a registered user.')
                continue

            parsed_reviewers.append({
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'affiliation': affiliation,
            })

        if errors:
            raise forms.ValidationError('\n'.join(errors))

        if not parsed_reviewers:
            raise forms.ValidationError('No valid reviewers found in the list.')

        return parsed_reviewers


class AssignGuestReviewerForm(forms.Form):
    """Form for assigning a guest reviewer to a submission"""
    REVIEWER_TYPE_CHOICES = [
        ('existing_guest', 'Existing Guest Reviewer'),
        ('new_guest', 'New Guest Reviewer'),
        ('registered_user', 'Registered User'),
    ]

    reviewer_type = forms.ChoiceField(
        choices=REVIEWER_TYPE_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        initial='registered_user',
        label='Reviewer Type'
    )

    # For existing guest reviewer
    guest_reviewer = forms.ModelChoiceField(
        queryset=GuestReviewer.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Select Guest Reviewer',
        empty_label='-- Select a guest reviewer --'
    )

    # For new guest reviewer
    new_guest_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'reviewer@example.com'
        }),
        label='Email'
    )
    new_guest_first_name = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First Name'
        }),
        label='First Name'
    )
    new_guest_last_name = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last Name'
        }),
        label='Last Name'
    )
    new_guest_affiliation = forms.CharField(
        required=False,
        max_length=300,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Institution (optional)'
        }),
        label='Affiliation'
    )

    # For registered user (existing field)
    assigned_to = forms.ModelChoiceField(
        queryset=None,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Select User',
        empty_label='-- Select a reviewer --'
    )

    role = forms.ChoiceField(
        choices=Assignment.ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        initial='reviewer',
        label='Role'
    )

    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional notes for the reviewer...'
        }),
        label='Notes'
    )

    blinded = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Blind Review (hide author information)',
        help_text='If checked, author information will be hidden from the reviewer.'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set queryset for assigned_to field (reviewers and editors)
        from .models import CustomUser
        self.fields['assigned_to'].queryset = CustomUser.objects.filter(
            models.Q(profile__is_reviewer=True) | models.Q(profile__is_editor=True)
        ).distinct()

    def clean(self):
        """Validate that appropriate fields are filled based on reviewer_type"""
        cleaned_data = super().clean()
        reviewer_type = cleaned_data.get('reviewer_type')

        if reviewer_type == 'existing_guest':
            if not cleaned_data.get('guest_reviewer'):
                raise forms.ValidationError('Please select an existing guest reviewer.')

        elif reviewer_type == 'new_guest':
            required_fields = ['new_guest_email', 'new_guest_first_name', 'new_guest_last_name']
            for field in required_fields:
                if not cleaned_data.get(field):
                    field_name = field.replace('new_guest_', '').replace('_', ' ').title()
                    raise forms.ValidationError(f'{field_name} is required for new guest reviewer.')

            # Check if email already exists
            email = cleaned_data.get('new_guest_email')
            if email:
                if GuestReviewer.objects.filter(email=email).exists():
                    raise forms.ValidationError(f'Guest reviewer with email {email} already exists.')
                from .models import CustomUser
                if CustomUser.objects.filter(email=email).exists():
                    raise forms.ValidationError(f'Email {email} is already a registered user.')

        elif reviewer_type == 'registered_user':
            if not cleaned_data.get('assigned_to'):
                raise forms.ValidationError('Please select a registered user.')

        return cleaned_data


################### End Guest Reviewer Forms #########################


################### End Submission Workflow Forms #########################

################### Journal Role Forms #########################

class JournalRoleForm(forms.ModelForm):
    """Grant a user an editorial role on one journal.

    Identifies the user by email rather than a dropdown: the user list grows
    without bound, and an admin adding a colleague knows their email, not their
    position in a <select>.
    """
    email = forms.EmailField(
        label='User email',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'colleague@unijos.edu.ng',
        }),
        help_text='The user must already have an account on the platform.'
    )

    class Meta:
        model = JournalRole
        fields = ('role',)
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, journal=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.journal = journal

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        try:
            self.user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise forms.ValidationError(
                'No account with that email. Ask them to register first, '
                'then grant the role.'
            )
        if not self.user.is_active:
            raise forms.ValidationError('That account is deactivated.')
        return email

    def clean(self):
        cleaned = super().clean()
        user = getattr(self, 'user', None)
        role = cleaned.get('role')
        if user and role and self.journal:
            if JournalRole.objects.filter(
                user=user, journal=self.journal, role=role
            ).exists():
                raise forms.ValidationError(
                    f'{user.email} is already {dict(JournalRole.ROLE_CHOICES)[role]} '
                    f'of {self.journal.name}.'
                )
        return cleaned

    def save(self, commit=True, granted_by=None):
        role = super().save(commit=False)
        role.user = self.user
        role.journal = self.journal
        role.granted_by = granted_by
        if commit:
            role.save()
        return role


################### End Journal Role Forms #########################


################### Journal Content Forms (rubrics + checklist) #########################

class RubricForm(forms.ModelForm):
    """A review rubric / guideline entry for a journal."""
    class Meta:
        model = Rubric
        fields = ('title', 'content', 'order')
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Originality and significance',
            }),
            'content': CKEditorWidget(),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }
        help_texts = {
            'order': 'Lower numbers appear first.',
        }


class ChecklistItemForm(forms.ModelForm):
    """One submission-checklist item for a journal."""
    class Meta:
        model = ChecklistItem
        fields = ('text', 'help_text', 'required', 'is_active', 'order')
        widgets = {
            'text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. The manuscript follows the journal formatting guidelines',
            }),
            'help_text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional clarifying note',
            }),
            'required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }
        help_texts = {
            'required': 'Authors cannot submit without ticking a required item.',
            'is_active': 'Uncheck to retire an item without deleting past responses.',
            'order': 'Lower numbers appear first.',
        }


class JournalSettingsForm(forms.ModelForm):
    """
    A journal's own public profile, editable by its Chief Editor.

    Deliberately narrower than :class:`JournalForm`: ``slug``, ``department``,
    ``order`` and ``is_active`` decide where the journal sits in the site and
    stay with site administrators.
    """
    class Meta:
        model = Journal
        fields = ('name', 'abbreviation', 'tagline', 'about', 'logo', 'cover_image',
                  'issn_print', 'issn_online', 'published_by', 'contact_email')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'abbreviation': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'e.g. JJEL',
            }),
            'tagline': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. A peer-reviewed journal of English language studies',
            }),
            'about': CKEditorWidget(),
            'issn_print': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '0000-0000'}),
            'issn_online': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '0000-0000'}),
            'published_by': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Department of English, University of Jos',
            }),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'about': 'Aims and scope — the main text on the journal home page.',
            'logo': 'Shown on the journal card on the home page.',
            'cover_image': 'Wide banner image for the journal home page.',
        }


class IssueForm(forms.ModelForm):
    """One published edition of a journal."""
    class Meta:
        model = Issue
        fields = ('volume', 'number', 'year', 'title', 'description',
                  'published_date', 'document', 'cover_image',
                  'is_published', 'featured')
        widgets = {
            'volume': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 2'}),
            'number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 1'}),
            'year': forms.NumberInput(attrs={'class': 'form-control', 'min': 1900, 'max': 2200}),
            'title': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Optional: special issue title',
            }),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'published_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'document': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf'}),
            'cover_image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'document': 'Optional: the complete issue as one PDF, for readers to view or download.',
            'is_published': 'Uncheck to keep the issue hidden while you assemble it.',
            'featured': 'Featured issues appear on the site home page.',
        }

    def __init__(self, *args, journal=None, **kwargs):
        # unique_together is on (journal, volume, number), but the form never
        # exposes `journal` — so Django's own uniqueness check cannot run and a
        # duplicate would surface as an IntegrityError. Check it here instead.
        self.journal = journal or getattr(self.instance, 'journal', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        volume, number = cleaned.get('volume'), cleaned.get('number', '')
        if self.journal and volume:
            clash = Issue.objects.filter(
                journal=self.journal, volume=volume, number=number
            ).exclude(pk=self.instance.pk)
            if clash.exists():
                raise forms.ValidationError(
                    f'{self.journal.short_name} already has an issue for '
                    f'Volume {volume}({number}).'
                )
        return cleaned


class EditorialBoardMemberForm(forms.ModelForm):
    """A person on a journal's public editorial board."""
    class Meta:
        model = EditorialBoardMember
        fields = ('name', 'position', 'section', 'affiliation', 'email',
                  'photo', 'bio', 'user', 'order', 'is_active')
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'e.g. Prof. Jane Doe',
            }),
            'position': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'e.g. Editor-in-Chief',
            }),
            'section': forms.Select(attrs={'class': 'form-select'}),
            'affiliation': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'e.g. University of Jos',
            }),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'photo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'bio': CKEditorWidget(),
            'user': forms.Select(attrs={'class': 'form-select'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'user': 'Optional. Listing someone here grants no permissions — '
                    'use the Team tab for that.',
            'order': 'Lower numbers appear first within a section.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'].required = False
        self.fields['user'].empty_label = '— no portal account —'


class JournalPageForm(forms.ModelForm):
    """A policy or guide page belonging to one journal."""
    class Meta:
        model = JournalPage
        fields = ('title', 'slug', 'content', 'order', 'show_in_nav', 'is_published')
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'e.g. Submission Guide',
            }),
            'slug': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'e.g. submission-guide',
            }),
            'content': CKEditorWidget(),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'show_in_nav': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'slug': "Appears in the page's web address. Leave as suggested if unsure.",
            'show_in_nav': "Show in the journal's navigation bar.",
            'order': 'Lower numbers appear first.',
        }

    def __init__(self, *args, journal=None, **kwargs):
        # Same reason as IssueForm: unique_together spans `journal`, which this
        # form does not expose, so validate the pair by hand.
        self.journal = journal or getattr(self.instance, 'journal', None)
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False

    def clean_slug(self):
        from django.utils.text import slugify
        slug = self.cleaned_data.get('slug') or slugify(self.data.get('title', ''))
        if not slug:
            raise forms.ValidationError('Enter a title so a web address can be generated.')
        clash = JournalPage.objects.filter(journal=self.journal, slug=slug)
        if self.instance.pk:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError('This journal already has a page with that address.')
        return slug


################### End Journal Content Forms #########################


################### Volunteer Reviewer Application Forms #########################

class ReviewerApplicationForm(forms.ModelForm):
    """Public form for volunteering as a peer reviewer (no account required)."""

    # Honeypot: a real person leaves this empty; bots tend to fill every field.
    # It's visually hidden in the template and rejected server-side if filled.
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'tabindex': '-1', 'autocomplete': 'off', 'class': 'uj-hp',
        }),
        label='Leave this field blank',
    )

    class Meta:
        model = ReviewerApplication
        fields = [
            'first_name', 'last_name', 'email', 'affiliation', 'position',
            'qualifications', 'expertise_areas', 'journals_of_interest',
            'cv', 'statement',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'you@institution.edu'}),
            'affiliation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'University of Jos'}),
            'position': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Senior Lecturer'}),
            'qualifications': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Degrees, key publications, review experience...'}),
            'expertise_areas': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'e.g. Applied Linguistics, Phonology (comma-separated)'}),
            'journals_of_interest': forms.CheckboxSelectMultiple(),
            'cv': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf,.doc,.docx'}),
            'statement': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Why would you like to review for us?'}),
        }
        help_texts = {
            'expertise_areas': 'Separate areas with commas.',
            'journals_of_interest': 'Optional — which journals you would like to review for.',
            'cv': 'Optional — PDF or Word document.',
        }

    def clean_website(self):
        if self.cleaned_data.get('website'):
            raise forms.ValidationError('Spam detected.')
        return ''

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        # Block a second application while one is still pending.
        if ReviewerApplication.objects.filter(email__iexact=email, status='pending').exists():
            raise forms.ValidationError(
                'You already have an application under review. We will be in touch soon.'
            )
        return email

    def clean_cv(self):
        cv = self.cleaned_data.get('cv')
        if cv:
            ext = cv.name.split('.')[-1].lower()
            if ext not in ['pdf', 'doc', 'docx']:
                raise forms.ValidationError('CV must be a PDF or Word document.')
            if cv.size > 10 * 1024 * 1024:
                raise forms.ValidationError('File size must be under 10MB.')
        return cv


class ReviewerApplicationDecisionForm(forms.Form):
    """Editor's decision on an application."""
    DECISION_CHOICES = (
        ('approve_user', 'Approve — create a login account (reviewer signs in)'),
        ('approve_guest', 'Approve — add as a guest reviewer (token access, no login)'),
        ('reject', 'Decline this application'),
    )
    decision = forms.ChoiceField(
        choices=DECISION_CHOICES,
        widget=forms.RadioSelect(),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3,
                                     'placeholder': 'Optional note (included in the email to the applicant)...'}),
    )


################### End Volunteer Reviewer Application Forms #########################


################### Publication Fee Form #########################

class JournalFeeForm(forms.ModelForm):
    """Set a journal's publication fee (0 or inactive = free)."""
    class Meta:
        model = JournalFee
        fields = ('amount', 'currency', 'is_active')
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': '0.01'}),
            'currency': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'amount': 'Charged on acceptance, before publication.',
            'currency': 'ISO code, e.g. NGN.',
            'is_active': 'Uncheck to publish this journal free of charge.',
        }


################### End Publication Fee Form #########################
