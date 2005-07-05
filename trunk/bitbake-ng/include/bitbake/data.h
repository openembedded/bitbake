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

#ifndef _BB_DATA_H
# define _BB_DATA_H

# include <bitbake/common.h>
# include <glib/gtypes.h>

BITBAKE_HDR_BEGIN


/** @file data.h
 *  @brief Header for bitbake metadata handling */

/**
 *@brief Creates a new bitbake metadata store
 *
 *@return An empty bitbake metadata store
 */
BBAPI gpointer bb_data_new(void);

/**
 *Obtains the value of an bitbake variable
 *
 *@param data      The bitbake metadata store in question.
 *@param var       The variable name.
 *
 *@return The variable's value.
 */
BBAPI gchar *bb_data_lookup(gconstpointer data, gchar *var);


/**
 *Sets the value of an bitbake variable
 *
 *@param data      The bitbake metadata store in question.
 *@param var       The variable name.
 *@param val       The value to be set the variable to.
 *
 *@return TRUE if succeeded, FALSE if failed.
 */
BBAPI gboolean bb_data_insert(gpointer data, gchar *var, gchar *val);


/**
 *Deletes an bitbake variable
 *
 *@param data      The bitbake metadata store in question.
 *@param var       The variable name.
 *
 *@return TRUE if succeeded, FALSE if failed.
 */
BBAPI gboolean bb_data_remove(gpointer data, gchar *var);


#if 0
/**
 *Obtains a certain conditional value associated with an bitbake variable.
 *
 *An bitbake variable has a default value (that which is
 *accessed by the usual bb_data_insert api), and any
 *number of possible values which are bound to conditions.
 *
 *This function obtains one of those conditional values.
 *
 *@param data       The bitbake metadata store in question.
 *@param var        The variable name.
 *@param conditions The conditions which apply to the value we're
 *                  attempting to get.
 *
 *@return The conditional value.
 */
BBAPI gchar *bb_data_lookup_cond(gconstpointer data, gchar *var, gchar *conditions[2]);


/**
 *Sets a certain conditional value associated with an bitbake variable.
 *
 *An bitbake variable has a default value (that which is
 *accessed by the usual bb_data_insert api), and any
 *number of possible values which are bound to conditions.
 *
 *This function removes one of those conditional values.
 *
 *@param data       The bitbake metadata store in question.
 *@param var        The variable name.
 *@param val        The value to set this variable to when these conditions are true.
 *@param conditions The conditions which apply to the value we're
 *                  attempting to remove.
 *
 *@return TRUE if succeeded, FALSE if failed.
 */
BBAPI gboolean bb_data_insert_cond(gpointer data, gchar *var, gchar *val, gchar *conditions[2]);


/**
 *Deletes a certain conditional value associated with an bitbake variable.
 *
 *An bitbake variable has a default value (that which is
 *accessed by the usual bb_data_insert api), and any
 *number of possible values which are bound to conditions.
 *
 *This function removes one of those conditional values.
 *
 *@param data       The bitbake metadata store in question.
 *@param var        The variable name.
 *@param conditions The conditions which apply to the value we're
 *                  attempting to remove.
 *
 *@return TRUE if succeeded, FALSE if failed.
 */
BBAPI gboolean bb_data_remove_cond(gpointer data, gchar *var, gchar *conditions[2]);
#endif


/**
 *Obtains the value of one of the attributes of an bitbake variable.
 *
 *@param data      The bitbake metadata store in question.
 *@param var       The variable name.
 *@param attr      The attribute name.
 *
 *@return The attribute in question.
 */
BBAPI gchar *bb_data_lookup_attr(gconstpointer data, gchar *var, gchar *attr);


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
BBAPI gboolean bb_data_insert_attr(gpointer data, gchar *var, gchar *attr, gchar *val);


/**
 *Deletes a given attribute from an bitbake variable
 *
 *@param data      The bitbake metadata store in question.
 *@param var       The variable name.
 *@param attr      The attribute name.
 *
 *@return TRUE if succeeded, FALSE if failed.
 */
BBAPI gboolean bb_data_remove_attr(gpointer data, gchar *var, gchar *attr);

/**
 *Destroys a bitbake metadata store and all of its variables
 *
 */
BBAPI void bb_data_destroy(gpointer data);


BITBAKE_HDR_END

#endif /*_BB_DATA_H */
