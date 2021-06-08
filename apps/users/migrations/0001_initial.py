# Generated by Django 3.2.3 on 2021-06-06 06:04

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Profile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('just_joined', models.BooleanField(default=True)),
                ('yt_channel_id', models.CharField(default='', max_length=420)),
                ('import_in_progress', models.BooleanField(default=True)),
                ('access_token', models.TextField(default='')),
                ('refresh_token', models.TextField(default='')),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]