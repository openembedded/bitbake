from django.core.management.base import BaseCommand, CommandError
from orm.models import Build
import os



class Command(BaseCommand):
    args    = "buildId"
    help    = "Deletes selected build"

    def handle(self, buildId, *args, **options):
        b = Build.objects.get(pk = buildId)
        # theoretically, just b.delete() would suffice
        # however SQLite runs into problems when you try to
        # delete too many rows at once, so we delete some direct
        # relationships from Build manually.

        for t in b.target_set.all():
            t.delete()
        for t in b.task_build.all():
            t.delete()
        for p in b.package_set.all():
            p.delete()
        for lv in b.layer_version_build.all():
            lv.delete()
        for v in b.variable_build.all():
            v.delete()
        for l in b.logmessage_set.all():
            l.delete()

        # this should take care of the rest
        b.delete()

