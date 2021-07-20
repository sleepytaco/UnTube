# Generated by Django 3.2.3 on 2021-07-20 16:14

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('main', '0037_alter_video_num_of_accesses'),
    ]

    operations = [
        migrations.AddField(
            model_name='pin',
            name='untube_user',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='pins', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='playlistitem',
            name='video',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='main.video'),
        ),
    ]
