/*
 * BinReloc - a library for creating relocatable executables
 * Written by: Mike Hearn <mike@theoretic.com>
 *             Hongli Lai <h.lai@chello.nl>
 * http://autopackage.org/
 * 
 * This source code is public domain. You can relicense this code
 * under whatever license you want.
 *
 * NOTE: if you're using C++ and are getting "undefined reference
 * to br_*", try renaming prefix.c to prefix.cpp
 */

/* WARNING, BEFORE YOU MODIFY PREFIX.C:
 *
 * If you make changes to any of the functions in prefix.c, you MUST
 * change the BR_NAMESPACE macro (in prefix.h).
 * This way you can avoid symbol table conflicts with other libraries
 * that also happen to use BinReloc.
 *
 * Example:
 * #define BR_NAMESPACE(funcName) foobar_ ## funcName
 * --> expands br_locate to foobar_br_locate
 */

#ifndef _PREFIX_C_
#define _PREFIX_C_

#ifndef BR_PTHREADS
	/* Change 1 to 0 if you don't want pthread support */
	#define BR_PTHREADS 1
#endif /* BR_PTHREADS */

#include <stdlib.h>
#include <stdio.h>
#include <pthread.h>
#include <limits.h>
#include <string.h>
#include "binreloc.h"

#ifdef __cplusplus
extern "C" {
#endif /* __cplusplus */


#undef NULL
#define NULL ((void *) 0)

#ifdef __GNUC__
	#define br_return_val_if_fail(expr,val) if (!(expr)) {fprintf (stderr, "** BinReloc (%s): assertion %s failed\n", __PRETTY_FUNCTION__, #expr); return val;}
#else
	#define br_return_val_if_fail(expr,val) if (!(expr)) return val
#endif /* __GNUC__ */


#ifdef ENABLE_BINRELOC
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/param.h>
#include <unistd.h>


/**
 * br_locate:
 * symbol: A symbol that belongs to the app/library you want to locate.
 * Returns: A newly allocated string containing the full path of the
 *	    app/library that func belongs to, or NULL on error. This
 *	    string should be freed when not when no longer needed.
 *
 * Finds out to which application or library symbol belongs, then locate
 * the full path of that application or library.
 * Note that symbol cannot be a pointer to a function. That will not work.
 *
 * Example:
 * --> main.c
 * #include "prefix.h"
 * #include "bitbake-ng.h"
 *
 * int main (int argc, char *argv[]) {
 *	printf ("Full path of this app: %s\n", br_locate (&argc));
 *	bitbake-ng_start ();
 *	return 0;
 * }
 *
 * --> bitbake-ng.c starts here
 * #include "prefix.h"
 *
 * void bitbake-ng_start () {
 *	--> "" is a symbol that belongs to bitbake-ng (because it's called
 *	--> from bitbake-ng_start()); that's why this works.
 *	printf ("bitbake-ng is located in: %s\n", br_locate (""));
 * }
 */
char *
br_locate (void *symbol)
{
	char line[5000];
	FILE *f;
	char *path;

	br_return_val_if_fail (symbol != NULL, NULL);

	f = fopen ("/proc/self/maps", "r");
	if (!f)
		return NULL;

	while (!feof (f))
	{
		unsigned int start, end;

		if (!fgets (line, sizeof (line), f))
			continue;
		if (!strstr (line, " r-xp ") || !strchr (line, '/'))
			continue;

		sscanf (line, "%x-%x ", &start, &end);
		if (((unsigned int) symbol) >= start && ((unsigned int) symbol) < end)
		{
			char *tmp;
			size_t len;

			/* Extract the filename; it is always an absolute path */
			path = strchr (line, '/');

			/* Get rid of the newline */
			tmp = strrchr (path, '\n');
			if (tmp) *tmp = 0;

			/* Get rid of "(deleted)" */
			len = strlen (path);
			if (len > 10 && strcmp (path + len - 10, " (deleted)") == 0)
			{
				tmp = path + len - 10;
				*tmp = 0;
			}

			fclose(f);
			return strdup (path);
		}
	}

	fclose (f);
	return NULL;
}


/**
 * br_locate_prefix:
 * symbol: A symbol that belongs to the app/library you want to locate.
 * Returns: A prefix. This string should be freed when no longer needed.
 *
 * Locates the full path of the app/library that symbol belongs to, and return
 * the prefix of that path, or NULL on error.
 * Note that symbol cannot be a pointer to a function. That will not work.
 *
 * Example:
 * --> This application is located in /usr/bin/foo
 * br_locate_prefix (&argc);   --> returns: "/usr"
 */
char *
br_locate_prefix (void *symbol)
{
	char *path, *prefix;

	br_return_val_if_fail (symbol != NULL, NULL);

	path = br_locate (symbol);
	if (!path) return NULL;

	prefix = br_extract_prefix (path);
	free (path);
	return prefix;
}


/**
 * br_prepend_prefix:
 * symbol: A symbol that belongs to the app/library you want to locate.
 * path: The path that you want to prepend the prefix to.
 * Returns: The new path, or NULL on error. This string should be freed when no
 *	    longer needed.
 *
 * Gets the prefix of the app/library that symbol belongs to. Prepend that prefix to path.
 * Note that symbol cannot be a pointer to a function. That will not work.
 *
 * Example:
 * --> The application is /usr/bin/foo
 * br_prepend_prefix (&argc, "/share/foo/data.png");   --> Returns "/usr/share/foo/data.png"
 */
char *
br_prepend_prefix (void *symbol, char *path)
{
	char *tmp, *newpath;

	br_return_val_if_fail (symbol != NULL, NULL);
	br_return_val_if_fail (path != NULL, NULL);

	tmp = br_locate_prefix (symbol);
	if (!tmp) return NULL;

	if (strcmp (tmp, "/") == 0)
		newpath = strdup (path);
	else
		newpath = br_strcat (tmp, path);

	/* Get rid of compiler warning ("br_prepend_prefix never used") */
	if (0) br_prepend_prefix (NULL, NULL);

	free (tmp);
	return newpath;
}

#endif /* ENABLE_BINRELOC */


/* Pthread stuff for thread safetiness */
#if BR_PTHREADS

static pthread_key_t br_thread_key;
static pthread_once_t br_thread_key_once = PTHREAD_ONCE_INIT;


static void
br_thread_local_store_fini ()
{
	char *specific;

	specific = (char *) pthread_getspecific (br_thread_key);
	if (specific)
	{
		free (specific);
		pthread_setspecific (br_thread_key, NULL);
	}
	pthread_key_delete (br_thread_key);
	br_thread_key = 0;
}


static void
br_str_free (void *str)
{
	if (str)
		free (str);
}


static void
br_thread_local_store_init ()
{
	if (pthread_key_create (&br_thread_key, br_str_free) == 0)
		atexit (br_thread_local_store_fini);
}

#else /* BR_PTHREADS */

static char *br_last_value = NULL;

static void
br_free_last_value ()
{
	if (br_last_value)
		free (br_last_value);
}

#endif /* BR_PTHREADS */


/**
 * br_thread_local_store:
 * str: A dynamically allocated string.
 * Returns: str. This return value must not be freed.
 *
 * Store str in a thread-local variable and return str. The next
 * you run this function, that variable is freed too.
 * This function is created so you don't have to worry about freeing
 * strings.
 *
 * Example:
 * char *foo;
 * foo = thread_local_store (strdup ("hello")); --> foo == "hello"
 * foo = thread_local_store (strdup ("world")); --> foo == "world"; "hello" is now freed.
 */
const char *
br_thread_local_store (char *str)
{
	#if BR_PTHREADS
		char *specific;

		pthread_once (&br_thread_key_once, br_thread_local_store_init);

		specific = (char *) pthread_getspecific (br_thread_key);
		br_str_free (specific);
		pthread_setspecific (br_thread_key, str);

	#else /* BR_PTHREADS */
		static int initialized = 0;

		if (!initialized)
		{
			atexit (br_free_last_value);
			initialized = 1;
		}

		if (br_last_value)
			free (br_last_value);
		br_last_value = str;
	#endif /* BR_PTHREADS */

	return (const char *) str;
}


/**
 * br_strcat:
 * str1: A string.
 * str2: Another string.
 * Returns: A newly-allocated string. This string should be freed when no longer needed.
 *
 * Concatenate str1 and str2 to a newly allocated string.
 */
char *
br_strcat (const char *str1, const char *str2)
{
	char *result;

	if (!str1) str1 = "";
	if (!str2) str2 = "";

	result = (char *) calloc (sizeof (char), strlen (str1) + strlen (str2) + 1);
	result = strcpy (result, str1);
	result = strcat (result, str2);
	return result;
}


/* Emulates glibc's strndup() */
static char *
br_strndup (char *str, size_t size)
{
	char *result = NULL;
	size_t len;

	br_return_val_if_fail (str != NULL, NULL);

	len = strlen (str);
	if (!len) return strdup ("");

	result = (char *) calloc (sizeof (char), len + 1);
	memcpy (result, str, size);
	return result;
}


/**
 * br_extract_dir:
 * path: A path.
 * Returns: A directory name. This string should be freed when no longer needed.
 *
 * Extracts the directory component of path. Similar to g_dirname() or the dirname
 * commandline application.
 *
 * Example:
 * br_extract_dir ("/usr/local/foobar");  --> Returns: "/usr/local"
 */
char *
br_extract_dir (const char *path)
{
	char *end, *result;

	br_return_val_if_fail (path != NULL, NULL);

	end = strrchr (path, '/');
	if (!end) return strdup (".");

	while (end > path && *end == '/')
		end--;
	result = br_strndup ((char *) path, end - path + 1);
	if (!*result)
	{
		free (result);
		return strdup ("/");
	} else
		return result;
}


/**
 * br_extract_prefix:
 * path: The full path of an executable or library.
 * Returns: The prefix, or NULL on error. This string should be freed when no longer needed.
 *
 * Extracts the prefix from path. This function assumes that your executable
 * or library is installed in an LSB-compatible directory structure.
 *
 * Example:
 * br_extract_prefix ("/usr/bin/gnome-panel");   --> Returns "/usr"
 * br_extract_prefix ("/usr/local/bitbake-ng.so");   --> Returns "/usr/local"
 */
char *
br_extract_prefix (const char *path)
{
	char *end, *tmp, *result;

	br_return_val_if_fail (path != NULL, NULL);

	if (!*path) return strdup ("/");
	end = strrchr (path, '/');
	if (!end) return strdup (path);

	tmp = br_strndup ((char *) path, end - path);
	if (!*tmp)
	{
		free (tmp);
		return strdup ("/");
	}
	end = strrchr (tmp, '/');
	if (!end) return tmp;

	result = br_strndup (tmp, end - tmp);
	free (tmp);

	if (!*result)
	{
		free (result);
		result = strdup ("/");
	}

	return result;
}


#ifdef __cplusplus
}
#endif /* __cplusplus */

#endif /* _PREFIX_C */
