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

/** @file check_bitbake_data.c
 *  @brief First group of metadata tests */

#include <stdlib.h>
#include <string.h>
#include <glib.h>
#include <check.h>
#include <bitbake.h>

/**
 * Test the creation and destruction of a struct bb_data
 * using the bb_data_new() and bb_data_destroy() functions.
 */

START_TEST (test_data_create_destroy)
{
    gpointer data;

    data = bb_data_new();
    if (data == NULL)
        fail("Metadata store allocation returned a NULL pointer");
    bb_data_destroy(data);
}
END_TEST

START_TEST (test_data_var_insert)
{
    gpointer data;
    gchar *var, *val;

    data = bb_data_new();
    var = g_strdup("CC");
    val = g_strdup("gcc");

    bb_data_insert(data, var, val);
}
END_TEST

START_TEST (test_data_var_lookup)
{
    gpointer data;
    gchar *var, *val;

    data = bb_data_new();

    var = g_strdup("CC");
    val = g_strdup("gcc");
    bb_data_insert(data, var, val);

    val = bb_data_lookup(data, "CC");
    if (strcmp(val, "gcc") != 0)
        fail("CC does not have the correct value");

    bb_data_destroy(data);
}
END_TEST

START_TEST (test_data_var_remove)
{
    gpointer data;
    gchar *var, *val;

    data = bb_data_new();

    var = g_strdup("CC");
    val = g_strdup("gcc");
    bb_data_insert(data, var, val);

    bb_data_remove(data, var);

    bb_data_destroy(data);
}
END_TEST

Suite *bitbake_data_suite(void)
{
    Suite *s = suite_create("Bitbake Data");
    TCase *tc_core = tcase_create("Core");
    TCase *tc_var = tcase_create("Variable");

    suite_add_tcase (s, tc_core);
    suite_add_tcase (s, tc_var);

    tcase_add_test(tc_core, test_data_create_destroy);

    tcase_add_test(tc_var, test_data_var_insert);
    tcase_add_test(tc_var, test_data_var_lookup);
    tcase_add_test(tc_var, test_data_var_remove);
    return s;
}

int main(void)
{
    int nf;
    Suite *s = bitbake_data_suite();
    SRunner *sr = srunner_create(s);
    srunner_run_all(sr, CK_NORMAL);
    nf = srunner_ntests_failed(sr);
    srunner_free(sr);
    return (nf == 0) ? EXIT_SUCCESS : EXIT_FAILURE;
}
