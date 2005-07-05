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

#ifndef _BITBAKE_DATA_COMMON_H
# define _BITBAKE_DATA_COMMON_H

# ifdef __cplusplus
#  define BBDATA_HDR_BEGIN extern "C" {
#  define BBDATA_HDR_END }
# else
#  define BBDATA_HDR_BEGIN
#  define BBDATA_HDR_END
# endif /* __cplusplus */

BBDATA_HDR_BEGIN

/** @file common.h
 *  @brief Header for bitbake's commonly used macros */

/* Shared library support */
# ifdef WIN32
#  define BBDATA_IMPORT __declspec(dllimport)
#  define BBDATA_EXPORT __declspec(dllexport)
#  define BBDATA_DLLLOCAL
#  define BBDATA_DLLPUBLIC
# else
#  define BBDATA_IMPORT
#  ifdef GCC_HASCLASSVISIBILITY
#   define BBDATA_EXPORT __attribute__ ((visibility("default")))
#   define BBDATA_DLLLOCAL __attribute__ ((visibility("hidden")))
#   define BBDATA_DLLPUBLIC __attribute__ ((visibility("default")))
#  else
#   define BBDATA_EXPORT
#   define BBDATA_DLLLOCAL
#   define BBDATA_DLLPUBLIC
#  endif
# endif

/* Define BBDATA_API for DLL builds */
# ifdef BBDATA_DLL
#  ifdef BBDATA_DLL_EXPORTS
#   define BBDATA_API BBDATA_EXPORT
#  else
#   define BBDATA_API BBDATA_IMPORT
#  endif /* BBDATA_DLL_EXPORTS */
# else
#  define BBDATA_API
# endif /* BBDATA_DLL */

/* Throwable classes must always be visible on GCC in all binaries */
# ifdef WIN32
#  define BBDATA_EXCEPTIONAPI(api) api
# elif defined(GCC_HASCLASSVISIBILITY)
#  define BBDATA_EXCEPTIONAPI(api) BBDATA_EXPORT
# else
#  define BBDATA_EXCEPTIONAPI(api)
# endif

BBDATA_HDR_END

#endif /* _BITBAKE_DATA_COMMON_H */
