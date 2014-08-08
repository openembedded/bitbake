from django.contrib import admin
from django.contrib.admin.filters import RelatedFieldListFilter
from .models import Branch, LayerSource, ToasterSetting

class LayerSourceAdmin(admin.ModelAdmin):
    pass

class BranchAdmin(admin.ModelAdmin):
    pass

class ToasterSettingAdmin(admin.ModelAdmin):
    pass

admin.site.register(LayerSource, LayerSourceAdmin)
admin.site.register(Branch, BranchAdmin)
admin.site.register(ToasterSetting, ToasterSettingAdmin)

