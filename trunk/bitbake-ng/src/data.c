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

/** @file data.c
 *  @brief Bitbake Metadata Handling Code */

# include <bitbake/common.h>
# include <bitbake/data.h>
# include <bitbake/data-private.h>
# include <glib.h>

static void _bb_data_destroy_element(gpointer data)
{
    g_free(data);
}

static void _bb_data_var_list_free(gpointer data, gpointer user_data)
{
    user_data=user_data;
    g_free(data);
}

static void _bb_data_destroy_var(gpointer data)
{
    struct bb_var *var = data;
    g_free(var->key);
    g_free(var->val);
    g_list_foreach(var->chunks, _bb_data_var_list_free, NULL);
    g_list_free(var->chunks);
    g_list_foreach(var->referrers, _bb_data_var_list_free, NULL);
    g_list_free(var->referrers);
    g_hash_table_destroy(var->attributes);
}

gpointer bb_data_new(void)
{
    struct bb_data *data;

    data = g_new0(struct bb_data, 1);
    data->data = g_hash_table_new_full(g_str_hash, g_str_equal, _bb_data_destroy_element, _bb_data_destroy_var);

    return data;
}

gchar *bb_data_lookup(gconstpointer ptr, gchar *var)
{
    const struct bb_data *data = ptr;
    const struct bb_var *bbvar;

    g_return_val_if_fail(G_LIKELY(data != NULL), FALSE);
    g_return_val_if_fail(G_LIKELY(data->data != NULL), FALSE);
    g_return_val_if_fail(G_LIKELY(var != NULL), FALSE);

    bbvar = g_hash_table_lookup(data->data, var);
    return bbvar->val;
}

gboolean bb_data_insert(gpointer ptr, gchar *var, gchar *val)
{
    struct bb_data *data = ptr;
    struct bb_var *bbvar;
    struct bb_var_chunk *main_chunk;

    g_return_val_if_fail(G_LIKELY(data != NULL), FALSE);
    g_return_val_if_fail(G_LIKELY(data->data != NULL), FALSE);
    g_return_val_if_fail(G_LIKELY(var != NULL), FALSE);

    bbvar = g_new0(struct bb_var, 1);
    bbvar->attributes = g_hash_table_new_full(g_str_hash, g_str_equal, _bb_data_destroy_element, _bb_data_destroy_element);
    bbvar->key = var;

    /* FIXME: rip apart the string into its chunks, and update our referrers
     *        list based on our chunks which are variable references */
    main_chunk = g_new0(struct bb_var_chunk, 1);
    main_chunk->data = (void *)val;
    main_chunk->type = BB_VAR_STR;
    g_list_append(bbvar->chunks, main_chunk);

    /* FIXME: set our cached value correctly, using the values of the vars
     *        that we reference */
    bbvar->val = val;

    /* FIXME: need to check the hash table before inserting.  if this key
     *        already exists, then we need to update its value and update
     *        the cached value of any variables that reference us */
    g_hash_table_insert(data->data, var, bbvar);

    return TRUE;
}

gboolean bb_data_remove(gpointer ptr, gchar *var)
{
    struct bb_data *data = ptr;

    g_return_val_if_fail(G_LIKELY(data != NULL), FALSE);
    g_return_val_if_fail(G_LIKELY(data->data != NULL), FALSE);
    g_return_val_if_fail(G_LIKELY(var != NULL), FALSE);

    g_hash_table_remove(data->data, var);
    return TRUE;
}

gchar *bb_data_lookup_attr(gconstpointer ptr, gchar *var, gchar *attr)
{
    const struct bb_data *data = ptr;

    g_return_val_if_fail(G_LIKELY(data != NULL), FALSE);
    g_return_val_if_fail(G_LIKELY(data->data != NULL), FALSE);
    g_return_val_if_fail(G_LIKELY(var != NULL), FALSE);
    g_return_val_if_fail(G_LIKELY(attr != NULL), FALSE);

    return NULL;
}

gboolean bb_data_insert_attr(gpointer ptr, gchar *var, gchar *attr, gchar *val)
{
    struct bb_data *data = ptr;

    g_return_val_if_fail(G_LIKELY(data != NULL), FALSE);
    g_return_val_if_fail(G_LIKELY(data->data != NULL), FALSE);
    g_return_val_if_fail(G_LIKELY(var != NULL), FALSE);
    g_return_val_if_fail(G_LIKELY(attr != NULL), FALSE);
    g_return_val_if_fail(G_LIKELY(val != NULL), FALSE);

    g_assert_not_reached(); /* unimplemented */

    return FALSE;
}

gboolean bb_data_remove_attr(gpointer ptr, gchar *var, gchar *attr)
{
    struct bb_data *data = ptr;

    g_return_val_if_fail(G_LIKELY(data != NULL), FALSE);
    g_return_val_if_fail(G_LIKELY(data->data != NULL), FALSE);
    g_return_val_if_fail(G_LIKELY(var != NULL), FALSE);
    g_return_val_if_fail(G_LIKELY(attr != NULL), FALSE);

    g_assert_not_reached(); /* unimplemented */

    return FALSE;
}

void bb_data_destroy(gpointer ptr)
{
    struct bb_data *data = ptr;

    g_return_if_fail(G_LIKELY(data != NULL));

    g_hash_table_destroy(data->data);
    g_free(ptr);
}
