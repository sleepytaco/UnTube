# Generated by Django 3.2.3 on 2021-07-16 06:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0035_alter_tag_created_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='playlist',
            name='is_yt_mix',
            field=models.BooleanField(default=False),
        ),
    ]