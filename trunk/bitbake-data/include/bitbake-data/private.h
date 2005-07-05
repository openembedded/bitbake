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

#ifndef _BITBAKE_DATA_PRIVATE_H
# define _BITBAKE_DATA_PRIVATE_H
# ifdef BBDATA_DLL_EXPORTS

# include <bitbake-data/common.h>
# include <glib.h>

BBDATA_HDR_BEGIN


/** @file data-private.h
 *  @brief Private header for bitbake metadata handling */

/**
 * Data for a given recipe
 */
struct bb_data {
    gchar *recipe;
};

#if 0
/**
 * Bitbake variable chunk types
 */
enum bb_var_chunk_type {
    /**
     * Indicates that the variable chunk in question is a string
     */
    BB_VAR_STR,

    /**
     * Indicates that the variable chunk in question is a
     * reference to another bitbake variable.
     */
    BB_VAR_REF,
};


/**
 * \brief BitBake variable chunk
 *
 * BitBake variables consist of multiple pieces, including, but not
 * limited to, strings and references to other variables.
 */
struct bb_var_chunk {
    /**
     * Type of chunk (i.e. BB_VAR_REF, BBVAR_STR, etc)
     */
    enum bb_var_chunk_type type;

    /**
     * Pointer to this chunk's data
     */
    gpointer *data;
};


/**
 * BitBake variable
 */
struct bb_var {
    /**
     * Variable name
     */
    gchar *key;

    /**
     * Cached value (post-expansion)
     */
    gchar *val;

    /**
     * Uncached value (pre-expansion)
     */
    gchar *orig_val;

    /**
     * List of variable chunks (of type struct bb_var_chunk)
     */
    GList *chunks;

    /**
     * Dirty flag -- indicates whether the cached value needs to
     * be updated, most likely due to referees changing.
     */
    int dirty;

    /**
     * List of variables that refer to this variable
     */
    GList *referrers;

    /**
     * Hash table of bitbake variable "attributes".  Bitbake variable
     * attributes are metadata about our metadata.  This allows us to
     * set flags about the metadata.  For example, we can specify the
     * interpreter for a given block of executable code.
     *
     * The hash table is attribute name -> gcchar *.
     */
    GHashTable *attributes;
};

/**
 * BitBake Datastore
 */
struct bb_data {
    /**
     * Links to context / higher scopes
     */
    GList *parents;

    /**
     * Hash table of variable name -> struct bb_var
     */
    GHashTable *data;
};
#endif


BBDATA_HDR_BEGIN

#endif /* BBDATA_DLL_EXPORTS */
#endif /* _BITBAKE_DATA_PRIVATE_H */
