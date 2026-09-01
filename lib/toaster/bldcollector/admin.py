#
# SPDX-License-Identifier: GPL-2.0-only
#

from django.contrib import admin
from orm.models import BitbakeVersion, Release, ToasterSetting, Layer_Version
from django import forms
import django.db.models as models


@admin.register(BitbakeVersion)
class BitbakeVersionAdmin(admin.ModelAdmin):

    # we override the formfield for db URLField
    # because of broken URL validation

    def formfield_for_dbfield(self, db_field, **kwargs):
        if isinstance(db_field, models.fields.URLField):
            return forms.fields.CharField()
        return super(BitbakeVersionAdmin, self).formfield_for_dbfield(
            db_field, **kwargs)


@admin.register(Release)
class ReleaseAdmin(admin.ModelAdmin):
    pass


@admin.register(ToasterSetting)
class ToasterSettingAdmin(admin.ModelAdmin):
    pass


@admin.register(Layer_Version)
class LayerVersionsAdmin(admin.ModelAdmin):
    pass

