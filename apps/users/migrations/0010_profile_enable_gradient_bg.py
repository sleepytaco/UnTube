# Generated by Django 3.2.3 on 2021-07-23 20:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0009_untube'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='enable_gradient_bg',
            field=models.BooleanField(default=False),
        ),
    ]