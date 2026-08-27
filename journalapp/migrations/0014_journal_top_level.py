"""
Make Journal the top-level entity and give each journal its own site.

Adds the fields a journal needs to stand on its own (slug, logo, about, ISSNs),
introduces Issue / EditorialBoardMember / JournalPage, and repoints Article at a
real Issue record. ``Article.volume`` and ``Article.issue`` were free text, so
they are renamed aside here and converted into Issue rows by 0015 before 0016
drops them.

``Journal.slug`` is added non-unique on purpose: existing rows get an empty slug
until 0015 fills them in, and 0016 then applies the unique constraint.
"""
import ckeditor.fields
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('journalapp', '0013_alter_submission_status_journalfee_payment'),
    ]

    operations = [
        # --- Journal: promote to top-level ---------------------------------
        migrations.AlterModelOptions(
            name='journal',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AddField(
            model_name='journal',
            name='slug',
            field=models.SlugField(
                default='', max_length=80,
                help_text="Used in the journal's web address, e.g. 'jjel'."),
        ),
        migrations.AddField(
            model_name='journal',
            name='abbreviation',
            field=models.CharField(
                blank=True, max_length=20,
                help_text="Short form, e.g. 'JJEL'. Shown on the journal card when no logo is set."),
        ),
        migrations.AddField(
            model_name='journal',
            name='tagline',
            field=models.CharField(
                blank=True, max_length=255,
                help_text='One line shown under the journal name.'),
        ),
        migrations.AddField(
            model_name='journal',
            name='about',
            field=ckeditor.fields.RichTextField(
                blank=True,
                help_text="Aims and scope — the main text on the journal's home page."),
        ),
        migrations.AddField(
            model_name='journal',
            name='logo',
            field=models.ImageField(
                blank=True, null=True, upload_to='journal_logos',
                help_text='Square-ish logo used on the journal cards.'),
        ),
        migrations.AddField(
            model_name='journal',
            name='issn_print',
            field=models.CharField(blank=True, max_length=20, verbose_name='ISSN (Print)'),
        ),
        migrations.AddField(
            model_name='journal',
            name='issn_online',
            field=models.CharField(blank=True, max_length=20, verbose_name='ISSN (Online)'),
        ),
        migrations.AddField(
            model_name='journal',
            name='published_by',
            field=models.CharField(
                blank=True, max_length=255,
                help_text="e.g. 'Department of English, University of Jos'."),
        ),
        migrations.AddField(
            model_name='journal',
            name='contact_email',
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name='journal',
            name='order',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Controls the order journals appear in on the home page.'),
        ),
        migrations.AddField(
            model_name='journal',
            name='is_active',
            field=models.BooleanField(
                default=True,
                help_text='Untick to hide this journal from the public site.'),
        ),
        migrations.AlterField(
            model_name='journal',
            name='department',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='journals', to='journalapp.department',
                help_text='Optional internal grouping. Not shown to visitors.'),
        ),

        # --- Issue ---------------------------------------------------------
        migrations.CreateModel(
            name='Issue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('volume', models.CharField(max_length=20, help_text="e.g. '2'")),
                ('number', models.CharField(blank=True, max_length=20,
                                            help_text="Issue number, e.g. '1'")),
                ('year', models.PositiveIntegerField()),
                ('title', models.CharField(
                    blank=True, max_length=255,
                    help_text='Optional name, for a special or themed issue.')),
                ('description', models.TextField(blank=True)),
                ('cover_image', models.ImageField(blank=True, null=True,
                                                  upload_to='issue_covers/')),
                ('document', models.FileField(
                    blank=True, null=True, upload_to='issues/',
                    help_text='The complete issue as a single PDF, for viewing and download.')),
                ('published_date', models.DateField()),
                ('is_published', models.BooleanField(
                    default=True,
                    help_text='Untick to keep this issue hidden while you prepare it.')),
                ('featured', models.BooleanField(
                    default=False, help_text='Feature this issue on the home page.')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('journal', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='issues', to='journalapp.journal')),
                ('uploaded_by', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='issues_uploaded', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-year', '-volume', '-number'],
                'unique_together': {('journal', 'volume', 'number')},
            },
        ),

        # --- EditorialBoardMember ------------------------------------------
        migrations.CreateModel(
            name='EditorialBoardMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('position', models.CharField(
                    max_length=120,
                    help_text="e.g. 'Editor-in-Chief', 'Managing Editor'.")),
                ('section', models.CharField(
                    choices=[('board', 'Editorial Board'),
                             ('consultants', 'Editorial Consultants'),
                             ('advisory', 'Advisory Board')],
                    default='board', max_length=20)),
                ('affiliation', models.CharField(blank=True, max_length=255)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('photo', models.ImageField(blank=True, null=True, upload_to='board_photos/')),
                ('bio', ckeditor.fields.RichTextField(blank=True)),
                ('order', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('journal', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='board_members', to='journalapp.journal')),
                ('user', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='board_memberships', to=settings.AUTH_USER_MODEL,
                    help_text="Optional: link to this person's portal account.")),
            ],
            options={'ordering': ['section', 'order', 'name']},
        ),

        # --- JournalPage ----------------------------------------------------
        migrations.CreateModel(
            name='JournalPage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('slug', models.SlugField(max_length=80,
                                          help_text="Used in the page's web address.")),
                ('content', ckeditor.fields.RichTextField()),
                ('order', models.PositiveIntegerField(default=0)),
                ('show_in_nav', models.BooleanField(
                    default=True,
                    help_text="Show this page in the journal's navigation bar.")),
                ('is_published', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('journal', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pages', to='journalapp.journal')),
            ],
            options={
                'ordering': ['order', 'title'],
                'unique_together': {('journal', 'slug')},
            },
        ),

        # --- Article: free-text volume/issue -> Issue FK --------------------
        # Renamed rather than dropped so 0015 can read the old values.
        migrations.RenameField(
            model_name='article', old_name='volume', new_name='legacy_volume'),
        migrations.RenameField(
            model_name='article', old_name='issue', new_name='legacy_issue'),
        migrations.AddField(
            model_name='article',
            name='issue',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='articles', to='journalapp.issue'),
        ),
    ]
