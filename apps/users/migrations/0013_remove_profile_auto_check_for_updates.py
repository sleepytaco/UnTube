# Generated by Django 3.2.3 on 2021-08-02 02:43

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0012_alter_profile_hide_unavailable_videos'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='profile',
            name='auto_check_for_updates',
        ),
    ]