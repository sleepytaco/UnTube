from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from backend.users.models import Profile


# Register your models here.
class ProfileResource(resources.ModelResource):

    class Meta:
        model = Profile


class ProfileAdmin(ImportExportModelAdmin):
    resource_class = ProfileResource
    list_display = ('untube_user', 'access_token', 'refresh_token')
    list_filter = ('created_at',)


admin.site.register(Profile, ProfileAdmin)
