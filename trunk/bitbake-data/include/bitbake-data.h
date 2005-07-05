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

#ifndef _BITBAKE_DATA_H
# define _BITBAKE_DATA_H

# include <bitbake-data/common.h>

BBDATA_HDR_BEGIN


/** @file bitbake-data.h
 *  @brief Header for bitbake metadata handling */

/**
 *@brief Creates a new bitbake metadata store
 *
 *@param recipe    A unique identifier for a given recipe for use in the store.
 *                 The most common case would be to pass the full path + filename
 *                 of the recipe in the filesystem.
 *
 *@return A bitbake datastore that's associated to the recipe.
 *        Will be empty if we have no info about this recipe, or if the store backend
 *        is not persistant.
 */
BBDATA_API void *bb_data_new(const unsigned char *recipe);

/**
 *@brief Obtains the last modification date of this metadata store.
 *
 *@param data      The bitbake metadata store in question.
 *
 *@return Last modification date of the datastore.
 */
BBDATA_API struct timeval bb_data_get_modif_date(void *data);

/**
 *@brief Obtains the value of an bitbake variable
 *
 *@param data      The bitbake metadata store in question.
 *@param var       The variable name.
 *
 *@return The variable's value as a unsigned char *.  This was malloc'd for the caller's use.
 *        The caller is therefore responsible for freeing this.
 */
BBDATA_API unsigned char *bb_data_lookup(const void *data, const unsigned char *var);


/**
 *Sets the value of an bitbake variable
 *
 *@param data      The bitbake metadata store in question.
 *@param var       The variable name.
 *@param val       The value to be set the variable to.
 *
 *@return TRUE if succeeded, FALSE if failed.
 */
BBDATA_API int bb_data_insert(void *data, const unsigned char *var, const unsigned char *val);


/**
 *Deletes an bitbake variable
 *
 *@param data      The bitbake metadata store in question.
 *@param var       The variable name.
 *
 *@return TRUE if succeeded, FALSE if failed.
 */
BBDATA_API int bb_data_remove(void *data, const unsigned char *var);


/**
 *Obtains the value of one of the attributes of an bitbake variable.
 *
 *@param data      The bitbake metadata store in question.
 *@param var       The variable name.
 *@param attr      The attribute name.
 *
 *@return The attribute in question as a unsigned char *.  This was malloc'd for the
 *        caller's use.  The caller is therefore responsible for freeing this.
 */
BBDATA_API unsigned char *bb_data_lookup_attr(const void *data, const unsigned char *var, const unsigned char *attr);


/**
 *Sets the value of one of the attributes of an bitbake variable.
 *
 *@param data      The bitbake metadata store in question.
 *@param var       The variable name.
 *@param val       The value to set this attribute to.
 *@param attr      The attribute name.
 *
 *@return TRUE if succeeded, FALSE if failed.
 */
BBDATA_API int bb_data_insert_attr(void *data, const unsigned char *var, const unsigned char *attr, const unsigned char *val);


/**
 *Deletes a given attribute from an bitbake variable
 *
 *@param data      The bitbake metadata store in question.
 *@param var       The variable name.
 *@param attr      The attribute name.
 *
 *@return TRUE if succeeded, FALSE if failed.
 */
BBDATA_API int bb_data_remove_attr(void *data, const unsigned char *var, const unsigned char *attr);

/**
 *@brief Deletes a given attribute from an bitbake variable
 *
 *@param data      The bitbake metadata store in question.
 *@param flush     This parameter only makes sense for persistant datastores.
 *                 for those, we need a means of indicating when the data can
 *                 truly be removed, when is no longer needed.  That is the
 *                 purpose of this parameter.
 */
BBDATA_API void bb_data_destroy(void *data, int flush);


BBDATA_HDR_END

#endif /*_BITBAKE_DATA_H */
