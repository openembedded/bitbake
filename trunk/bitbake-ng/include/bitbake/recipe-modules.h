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

#ifndef _BB_RECIPE_MODULES_H
# define _BB_RECIPE_MODULES_H

# include <bitbake/common.h>
# include <glib/gtypes.h>

BITBAKE_HDR_BEGIN


/** @file recipe-modules.h
 *  @brief Header for bitbake recipe handling (backend modules) */

BBAPI gboolean bb_recipe_load_parsers();
BBAPI gboolean bb_recipe_register_parser();
BBAPI void bb_recipe_unregister_parser();
BBAPI void bb_recipe_unload_parsers();

BBAPI gboolean bb_recipe_load_workers();
BBAPI gboolean bb_recipe_register_worker();
BBAPI void bb_recipe_unregister_worker();
BBAPI void bb_recipe_unload_workers();


BITBAKE_HDR_END

#endif /* _BB_RECIPE_MODULES_H */
