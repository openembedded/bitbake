/* ex:ts=4:sw=4:sts=4:et
 * -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
 *
 * Copyright (C) 2004, 2005 Chris Larson <kergoth@handhelds.org>
 *
 * Permission is hereby granted, free of charge, to any person obtaining a
 * copy of this software and associated documentation files (the "Software"),
 * to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense,
 * and/or sell copies of the Software, and to permit persons to whom the
 * Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 * FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
 * DEALINGS IN THE SOFTWARE.
 */

#ifndef _BB_RECIPE_H
# define _BB_RECIPE_H

# include <bitbake/common.h>
# include <glib/gtypes.h>

BITBAKE_HDR_BEGIN


/** @file recipe.h
 *  @brief Header for bitbake recipe handling (frontend) */

BBAPI gpointer bb_recipe_new(void);

BBAPI gboolean bb_recipe_load(gpointer recipe, gchar *location);
BBAPI gboolean bb_recipe_load_into_box(gpointer recipe, gpointer recipe_box, gchar *location);
BBAPI gboolean bb_recipe_sync(gpointer recipe);

BBAPI gboolean bb_recipe_add_parent(gpointer recipe, gpointer parent);
BBAPI gpointer bb_recipe_foreach_parent(gpointer recipe, char *callback);
BBAPI gboolean bb_recipe_remove_parent(gpointer recipe, gchar *parent_loc);

gchar *bb_recipe_lookup_var(gpointer recipe, gchar *var);
BBAPI gpointer bb_recipe_get_metadata(gpointer recipe);

BBAPI gboolean bb_recipe_can_execute(gpointer recipe);
BBAPI gboolean bb_recipe_execute(gpointer recipe);

BBAPI void bb_recipe_destroy(gpointer recipe);


BITBAKE_HDR_END

#endif /* _BB_RECIPE_H */
