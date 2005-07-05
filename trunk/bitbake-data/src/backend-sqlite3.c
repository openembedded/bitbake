/* vi:ts=8:sw=4:sts=4:et
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

#include <stdio.h> /* for printf */
#include <stdlib.h> /* for strtol */
#include <glib.h>
#include <sqlite3.h>
#include <bitbake-data.h>
#include <bitbake-data/private.h>

#include "config.h"

/**
 * Static structure to hold process wide information associated with
 * our bitbake data.  In this case, this holds our pointer to our open
 * sqlite3 database, its path, and so on.  Protected by a GStaticMutex.
 */
static struct {
    int initialized;
    GStaticMutex mutex;
    unsigned char *datapath;
    sqlite3 *db;
    guint users;
} bbdata_setup = {
    .initialized = FALSE,
    .mutex = G_STATIC_MUTEX_INIT,
};


static inline int add_tables()
{
    char **results;
    int nrow, ncol;
    int sret;

    sqlite3_get_table(bbdata_setup.db, "select name from sqlite_master where type = 'table' and name = 'recipes'",
                      &results, &nrow, &ncol, NULL);
    sqlite3_free_table(results);
    if (nrow < 1) {
        sret = sqlite3_exec(bbdata_setup.db, "create table recipes(key integer primary key, recipe text not null)",
                            NULL, 0, NULL);
        if (sret != SQLITE_OK)
            return FALSE;
    }

    sqlite3_get_table(bbdata_setup.db, "select name from sqlite_master where type = 'table' and name = 'scopes'",
                      &results, &nrow, &ncol, NULL);
    sqlite3_free_table(results);
    if (nrow < 1) {
        sret = sqlite3_exec(bbdata_setup.db,
                            "create table scopes(key integer primary key, priority integer, scope integer, recipe integer)",
                            NULL, 0, NULL);
        if (sret != SQLITE_OK)
            return FALSE;
    }

    sqlite3_get_table(bbdata_setup.db, "select name from sqlite_master where type = 'table' and name = 'vars'",
                      &results, &nrow, &ncol, NULL);
    sqlite3_free_table(results);
    if (nrow < 1) {
        sret = sqlite3_exec(bbdata_setup.db,
                            "create table vars(key integer primary key, var text not null, val text, recipe integer)",
                            NULL, 0, NULL);
        if (sret != SQLITE_OK)
            return FALSE;
    }
    return TRUE;
}


/**
 * Process wide initialization
 */
static int __bb_data_init(void)
{
    int ret = TRUE;
    const gchar *datapath = g_getenv("BBDATAPATH");
    unsigned char *fpath = NULL;
    guint sret;

    if (datapath)
        bbdata_setup.datapath = g_filename_to_utf8(datapath, -1, NULL, NULL, NULL);

    if (!bbdata_setup.datapath)
        bbdata_setup.datapath = g_build_path(LOCALSTATEDIR, "lib", "bitbake-data", NULL);

    fpath = g_build_filename(bbdata_setup.datapath, "data");

    sret = sqlite3_open(fpath, &bbdata_setup.db);
    if (sret)
        goto out_fail;

    ret = add_tables();
    if (!ret)
        goto out_fail;

    g_free(fpath);

    bbdata_setup.initialized = TRUE;
    return ret;

out_fail:
    sqlite3_close(bbdata_setup.db);
    g_free(bbdata_setup.datapath);
    g_free(fpath);
    return FALSE;
}

/**
 * Process wide shutdown
 */
static void __bb_data_shutdown(void)
{
    bbdata_setup.initialized = FALSE;
    sqlite3_close(bbdata_setup.db);
    g_free(bbdata_setup.datapath);
}

/**
 * Wrapper that initializes when necessary
 */
static inline int bb_data_init(void)
{
    if (!bbdata_setup.initialized)
        return __bb_data_init();
    else
        return TRUE;
}

/**
 * Wrapper that shuts down when necessary
 */
static inline void bb_data_shutdown(void)
{
    if (bbdata_setup.initialized) {
        bbdata_setup.users -= 1;

        if (bbdata_setup.users < 1)
            __bb_data_shutdown();
    }
}


static inline int add_recipe_to_db(const char *recipe)
{
    char **results;
    char *query;
    int nrow, ncol;

    query = sqlite3_mprintf("select key from recipes where recipe = '%q'", recipe);
    sqlite3_get_table(bbdata_setup.db, query, &results, &nrow, &ncol, NULL);
    sqlite3_free_table(results);
    sqlite3_free(query);
    if (nrow < 1) {
        int sret;
        char *insert = sqlite3_mprintf("insert into recipes values(NULL, '%q')", recipe);
        sret = sqlite3_exec(bbdata_setup.db, insert, NULL, 0, NULL);
        sqlite3_free(insert);
        if (sret != SQLITE_OK)
            return FALSE;
    }
    return TRUE;
}

void *bb_data_new(const unsigned char *recipe)
{
    void *ret = NULL;
    struct bb_data *data;
    int sret;

    g_static_mutex_lock(&bbdata_setup.mutex);
    if (!bb_data_init()) {
        g_static_mutex_unlock(&bbdata_setup.mutex);
        return ret;
    }

    bbdata_setup.users += 1;
    g_static_mutex_unlock(&bbdata_setup.mutex);

    ret = g_malloc0(sizeof(struct bb_data));
    data = (struct bb_data *)ret;
    data->recipe = g_strdup(recipe);

    sret = sqlite3_exec(bbdata_setup.db, "begin", NULL, 0, NULL);
    if (sret != SQLITE_OK)
        goto sqliteerror;

    if (!add_recipe_to_db(recipe))
        goto sqliteerror;

    sret = sqlite3_exec(bbdata_setup.db, "commit", NULL, 0, NULL);
    if (sret != SQLITE_OK)
        goto sqliteerror;
    return ret;
sqliteerror:
    sqlite3_exec(bbdata_setup.db, "rollback", NULL, 0, NULL);
    g_static_mutex_lock(&bbdata_setup.mutex);
    bbdata_setup.users -= 1;
    bb_data_shutdown();
    g_static_mutex_unlock(&bbdata_setup.mutex);
    g_free(ret);
    return NULL;
}

void bb_data_destroy(void *data, int flush)
{
    struct bb_data *d = (struct bb_data *)data;
    if (flush) {
        char *str;
#if 0
        str = sqlite3_mprintf("drop table '%q'", d->recipe);
        sqlite3_exec(bbdata_setup.db, str, NULL, 0, NULL);
        sqlite3_free(str);
#endif
        str = sqlite3_mprintf("delete from recipes where recipe = '%q'", d->recipe);
        sqlite3_exec(bbdata_setup.db, str, NULL, 0, NULL);
        sqlite3_free(str);
    }

    g_free(data);

    g_static_mutex_lock(&bbdata_setup.mutex);

    if (bbdata_setup.initialized) {
        bbdata_setup.users -= 1;

        if (bbdata_setup.users < 1) {
            bb_data_shutdown();
        }
    }

    g_static_mutex_unlock(&bbdata_setup.mutex);
}

unsigned char *bb_data_lookup(const void *data, const unsigned char *var)
{
    struct bb_data *d = (struct bb_data *)data;
    char **results;
    char *query;
    int nrow, ncol;
    unsigned char *ret = NULL;

    query = sqlite3_mprintf("select val from vars join scopes on vars.recipe = scopes.scope join recipes on recipes.key = scopes.recipe where var = '%q' and recipes.recipe = '%q' order by scopes.priority desc limit 1", var, d->recipe);
    sqlite3_get_table(bbdata_setup.db, query, &results, &nrow, &ncol, NULL);
    sqlite3_free(query);
    printf("nrow is %d\n", nrow);
    if (nrow > 0)
        if (results && results[1])
            ret = g_strdup(results[1]);
    sqlite3_free_table(results);
    return ret;
}

long __get_recipe_num(void *data)
{
    struct bb_data *d = (struct bb_data *)data;
    char *query;
    char **results;
    int nrow, ncol;
    long recipenum = 0;

    query = sqlite3_mprintf("select key from recipes where recipe = '%q'", d->recipe);
    sqlite3_get_table(bbdata_setup.db, query, &results, &nrow, &ncol, NULL);
    sqlite3_free(query);
    printf("nrow is %d", nrow);
    if (nrow > 0)
        if (results && results[1]) {
            recipenum = strtol(results[1], NULL, 10);
            printf("recipenum is %ld\n", recipenum);
        }
    sqlite3_free_table(results);
    return recipenum;
}

int bb_data_insert(void *data, const unsigned char *var, const unsigned char *val)
{
    char *query;
    int sret;
    long recipenum = __get_recipe_num(data);

    query = sqlite3_mprintf("insert into vars values(NULL, '%q', '%q', %d)", var, val, recipenum);
    sret = sqlite3_exec(bbdata_setup.db, query, NULL, 0, NULL);
    sqlite3_free(query);
    if (sret != SQLITE_OK)
        return FALSE;
    return TRUE;
}

int bb_data_remove(void *data, const unsigned char *var)
{
    struct bb_data *d = (struct bb_data *)data;
    char *query;
    int sret;
    long recipenum = __get_recipe_num(data);

    query = sqlite3_mprintf("delete from vars where var = '%q' and recipe = %d", d->recipe, var, recipenum);
    sret = sqlite3_exec(bbdata_setup.db, query, NULL, 0, NULL);
    sqlite3_free(query);
    if (sret != SQLITE_OK)
        return FALSE;
    return TRUE;
}

unsigned char *bb_data_lookup_attr(const void *data, const unsigned char *var, const unsigned char *attr)
{
    struct bb_data *d = (struct bb_data *)data;
    char **results;
    char *query;
    int nrow, ncol;
    unsigned char *ret = NULL;

    query = sqlite3_mprintf("select attr from '%q' where var = '%q' and attr not null and val = '%q'", d->recipe, var, attr);
    sqlite3_get_table(bbdata_setup.db, query, &results, &nrow, &ncol, NULL);
    sqlite3_free(query);
    if (nrow > 0)
        if (results && results[1])
            ret = g_strdup(results[1]);
    sqlite3_free_table(results);
    return ret;
}

int bb_data_insert_attr(void *data, const unsigned char *var, const unsigned char *attr, const unsigned char *val)
{
    struct bb_data *d = (struct bb_data *)data;
    char *query;
    int sret;

    query = sqlite3_mprintf("delete from '%q' where var = '%q' and attr not null and val = '%q'", d->recipe, var, attr);
    sret = sqlite3_exec(bbdata_setup.db, query, NULL, 0, NULL);
    sqlite3_free(query);

    query = sqlite3_mprintf("insert into '%q' values(NULL, '%q', '%q', '%q')", d->recipe, var, attr, val);
    sret = sqlite3_exec(bbdata_setup.db, query, NULL, 0, NULL);
    sqlite3_free(query);
    if (sret != SQLITE_OK)
        return FALSE;
    return TRUE;
}

int bb_data_remove_attr(void *data, const unsigned char *var, const unsigned char *attr)
{
    struct bb_data *d = (struct bb_data *)data;
    char *query;
    int sret;

    query = sqlite3_mprintf("delete from '%q' where var = '%q' and val = '%q' and attr not null", d->recipe, var, attr);
    sret = sqlite3_exec(bbdata_setup.db, query, NULL, 0, NULL);
    sqlite3_free(query);
    if (sret != SQLITE_OK)
        return FALSE;
    return TRUE;
}
