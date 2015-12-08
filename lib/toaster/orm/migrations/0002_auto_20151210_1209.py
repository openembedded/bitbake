# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orm', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='customimagerecipe',
            name='recipe_ptr',
            field=models.OneToOneField(parent_link=True, auto_created=True, default=None, serialize=False, to='orm.Recipe'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='customimagerecipe',
            name='base_recipe',
            field=models.ForeignKey(related_name='based_on_recipe', to='orm.Recipe'),
        ),
        migrations.AlterUniqueTogether(
            name='customimagerecipe',
            unique_together=set([]),
        ),
        migrations.RemoveField(
            model_name='customimagerecipe',
            name='id',
        ),
        migrations.RemoveField(
            model_name='customimagerecipe',
            name='name',
        ),
        migrations.RemoveField(
            model_name='customimagerecipe',
            name='packages',
        ),
    ]
