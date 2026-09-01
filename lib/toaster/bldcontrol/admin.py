#
# SPDX-License-Identifier: GPL-2.0-only
#

from django.contrib import admin
from .models import BuildEnvironment

@admin.register(BuildEnvironment)
class BuildEnvironmentAdmin(admin.ModelAdmin):
    pass

