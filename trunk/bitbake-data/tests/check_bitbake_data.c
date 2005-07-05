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
#include <check.h>
#include <bitbake-data.h>

/**
 * Test the creation and destruction of a struct bb_data
 * using the bb_data_new("test") and bb_data_destroy() functions.
 */

START_TEST (test_data_create_destroy)
{
    void *data;

    data = bb_data_new("test_data_create_destroy");
    if (data == NULL)
        fail("Metadata store allocation returned a NULL pointer");
    bb_data_destroy(data, 1);
}
END_TEST

START_TEST (test_data_var_insert)
{
    void *data;
    unsigned char *var, *val;
    int ret;

    data = bb_data_new("test_data_var_insert");
    var = "CC";
    val = "gcc";

    ret = bb_data_insert(data, var, val);
    if (!ret)
        fail("Failed to insert");
}
END_TEST

START_TEST (test_data_var_lookup)
{
    void *data;
    unsigned char *var, *val;
    int ret;

    data = bb_data_new("test_data_var_lookup");

    var = "CC";
    val = "gcc";
    ret = bb_data_insert(data, var, val);
    if (!ret)
        fail("Failed to insert");

    val = bb_data_lookup(data, "CC");
    if (!val)
        fail("bb_data_lookup(data, \"CC\") returned NULL");
    if (strcmp(val, "gcc") != 0)
        fail("CC does not have the correct value");

    bb_data_destroy(data, 1);
}
END_TEST

START_TEST (test_data_var_remove)
{
    void *data;
    unsigned char *var, *val;
    int ret;

    data = bb_data_new("test_data_var_remove");

    var = "CC";
    val = "gcc";
    ret = bb_data_insert(data, var, val);
    if (!ret)
        fail("Failed to insert");
    ret = bb_data_remove(data, var);
    if (!ret)
        fail("Failed to remove");

    bb_data_destroy(data, 1);
}
END_TEST

#if 0
START_TEST (test_data_attr_insert)
{
    void *data;
    unsigned char *var, *val, *attr;
    int ret;

    data = bb_data_new("test_data_attr_insert");
    var = "CC";
    attr = "export";
    val = "1";

    ret = bb_data_insert_attr(data, var, attr, val);
    if (!ret)
        fail("Failed to insert attribute");
}
END_TEST

START_TEST (test_data_attr_lookup)
{
    void *data;
    unsigned char *var, *val, *attr;
    int ret;

    data = bb_data_new("test_data_attr_lookup");

    var = "CC";
    attr = "export";
    val = "1";
    ret = bb_data_insert_attr(data, var, attr, val);
    if (!ret)
        fail("Failed to insert attribute");

    val = bb_data_lookup_attr(data, var, attr);
    if (!val)
        fail("bb_data_lookup_attr(data, \"CC\", \"export\") returned NULL");
    if (strcmp(val, "1") != 0)
        fail("CC export attribute does not have the correct value");

    bb_data_destroy(data, 1);
}
END_TEST

START_TEST (test_data_attr_remove)
{
    void *data;
    unsigned char *var, *val, *attr;
    int ret;

    data = bb_data_new("test_data_attr_remove");

    var = "CC";
    attr = "export";
    val = "1";
    ret = bb_data_insert_attr(data, var, attr, val);
    if (!ret)
        fail("Failed to insert attribute");
    ret = bb_data_remove_attr(data, var, attr);
    if (!ret)
        fail("Failed to remove attribute");

    bb_data_destroy(data, 1);
}
END_TEST
#endif

Suite *bitbake_data_suite(void)
{
    Suite *s = suite_create("Bitbake Data");
    TCase *tc_core = tcase_create("Core");
    TCase *tc_var = tcase_create("Variable");
    TCase *tc_attr = tcase_create("Variable Attributes");

    suite_add_tcase (s, tc_core);
    suite_add_tcase (s, tc_var);
    suite_add_tcase (s, tc_attr);

    tcase_add_test(tc_core, test_data_create_destroy);

//    tcase_add_test(tc_var, test_data_var_insert);
    tcase_add_test(tc_var, test_data_var_lookup);
//    tcase_add_test(tc_var, test_data_var_remove);

#if 0
    tcase_add_test(tc_attr, test_data_attr_insert);
    tcase_add_test(tc_attr, test_data_attr_lookup);
    tcase_add_test(tc_attr, test_data_attr_remove);
#endif
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
