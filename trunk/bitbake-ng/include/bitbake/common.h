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

#ifndef _BB_COMMON_H
# define _BB_COMMON_H

# ifdef __cplusplus
#  define BITBAKE_HDR_BEGIN extern "C" {
#  define BITBAKE_HDR_END }
# else
#  define BITBAKE_HDR_BEGIN
#  define BITBAKE_HDR_END
# endif /* __cplusplus */

BITBAKE_HDR_BEGIN

/** @file common.h
 *  @brief Header for bitbake's commonly used macros */

/* Shared library support */
# ifdef WIN32
#  define BBIMPORT __declspec(dllimport)
#  define BBEXPORT __declspec(dllexport)
#  define BBDLLLOCAL
#  define BBDLLPUBLIC
# else
#  define BBIMPORT
#  ifdef GCC_HASCLASSVISIBILITY
#   define BBEXPORT __attribute__ ((visibility("default")))
#   define BBDLLLOCAL __attribute__ ((visibility("hidden")))
#   define BBDLLPUBLIC __attribute__ ((visibility("default")))
#  else
#   define BBEXPORT
#   define BBDLLLOCAL
#   define BBDLLPUBLIC
#  endif
# endif

/* Define BBAPI for DLL builds */
# ifdef BBDLL
#  ifdef BBDLL_EXPORTS
#   define BBAPI BBEXPORT
#  else
#   define BBAPI BBIMPORT
#  endif /* BBDLL_EXPORTS */
# else
#  define BBAPI
# endif /* BBDLL */

/* Throwable classes must always be visible on GCC in all binaries */
# ifdef WIN32
#  define BBEXCEPTIONAPI(api) api
# elif defined(GCC_HASCLASSVISIBILITY)
#  define BBEXCEPTIONAPI(api) BBEXPORT
# else
#  define BBEXCEPTIONAPI(api)
# endif

BITBAKE_HDR_END

#endif /* _BITBAKE_H */
