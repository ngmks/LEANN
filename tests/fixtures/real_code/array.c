/*
   +----------------------------------------------------------------------+
   | Copyright (c) The PHP Group                                          |
   +----------------------------------------------------------------------+
   | This source file is subject to version 3.01 of the PHP license,      |
   | that is bundled with this package in the file LICENSE, and is        |
   | available through the world-wide-web at the following url:           |
   | https://www.php.net/license/3_01.txt                                 |
   | If you did not receive a copy of the PHP license and are unable to   |
   | obtain it through the world-wide-web, please send a note to          |
   | license@php.net so we can mail you a copy immediately.               |
   +----------------------------------------------------------------------+
   | Authors: Andi Gutmans <andi@php.net>                                 |
   |          Zeev Suraski <zeev@php.net>                                 |
   |          Rasmus Lerdorf <rasmus@php.net>                             |
   |          Andrei Zmievski <andrei@php.net>                            |
   |          Stig Venaas <venaas@php.net>                                |
   |          Jason Greene <jason@php.net>                                |
   +----------------------------------------------------------------------+
*/

#include "php.h"
#include "php_ini.h"
#include <stdarg.h>
#include <stdlib.h>
#include <math.h>
#include <time.h>
#include <string.h>
#include "zend_globals.h"
#include "zend_interfaces.h"
#include "php_array.h"
#include "basic_functions.h"
#include "php_string.h"
#include "php_math.h"
#include "zend_smart_str.h"
#include "zend_bitset.h"
#include "zend_exceptions.h"
#include "ext/random/php_random.h"
#include "zend_frameless_function.h"

/* {{{ defines */

#define DIFF_NORMAL			1
#define DIFF_KEY			2
#define DIFF_ASSOC			6
#define DIFF_COMP_DATA_NONE    -1
#define DIFF_COMP_DATA_INTERNAL 0
#define DIFF_COMP_DATA_USER     1
#define DIFF_COMP_KEY_INTERNAL  0
#define DIFF_COMP_KEY_USER      1

#define INTERSECT_NORMAL		1
#define INTERSECT_KEY			2
#define INTERSECT_ASSOC			6
#define INTERSECT_COMP_DATA_NONE    -1
#define INTERSECT_COMP_DATA_INTERNAL 0
#define INTERSECT_COMP_DATA_USER     1
#define INTERSECT_COMP_KEY_INTERNAL  0
#define INTERSECT_COMP_KEY_USER      1
/* }}} */

ZEND_DECLARE_MODULE_GLOBALS(array)

/* {{{ php_array_init_globals */
static void php_array_init_globals(zend_array_globals *array_globals)
{
	memset(array_globals, 0, sizeof(zend_array_globals));
}
/* }}} */

PHP_MINIT_FUNCTION(array) /* {{{ */
{
	ZEND_INIT_MODULE_GLOBALS(array, php_array_init_globals, NULL);

	return SUCCESS;
}
/* }}} */

PHP_MSHUTDOWN_FUNCTION(array) /* {{{ */
{
#ifdef ZTS
	ts_free_id(array_globals_id);
#endif

	return SUCCESS;
}
/* }}} */

static zend_never_inline ZEND_COLD int stable_sort_fallback(Bucket *a, Bucket *b) {
	if (Z_EXTRA(a->val) > Z_EXTRA(b->val)) {
		return 1;
	} else if (Z_EXTRA(a->val) < Z_EXTRA(b->val)) {
		return -1;
	} else {
		return 0;
	}
}

#define RETURN_STABLE_SORT(a, b, result) do { \
	int _result = (result); \
	if (EXPECTED(_result)) { \
		return _result; \
	} \
	return stable_sort_fallback((a), (b)); \
} while (0)

/* Generate inlined unstable and stable variants, and non-inlined reversed variants. */
#define DEFINE_SORT_VARIANTS(name) \
	static zend_never_inline int php_array_##name##_unstable(Bucket *a, Bucket *b) { \
		return php_array_##name##_unstable_i(a, b); \
	} \
	static zend_never_inline int php_array_##name(Bucket *a, Bucket *b) { \
		RETURN_STABLE_SORT(a, b, php_array_##name##_unstable_i(a, b)); \
	} \
	static zend_never_inline int php_array_reverse_##name##_unstable(Bucket *a, Bucket *b) { \
		return php_array_##name##_unstable(a, b) * -1; \
	} \
	static zend_never_inline int php_array_reverse_##name(Bucket *a, Bucket *b) { \
		RETURN_STABLE_SORT(a, b, php_array_reverse_##name##_unstable(a, b)); \
	} \

static zend_always_inline int php_array_key_compare_unstable_i(Bucket *f, Bucket *s) /* {{{ */
{
	zval first;
	zval second;

	if (f->key == NULL && s->key == NULL) {
		return (zend_long)f->h > (zend_long)s->h ? 1 : -1;
	} else if (f->key && s->key) {
		return zendi_smart_strcmp(f->key, s->key);
	}
	if (f->key) {
		ZVAL_STR(&first, f->key);
	} else {
		ZVAL_LONG(&first, f->h);
	}
	if (s->key) {
		ZVAL_STR(&second, s->key);
	} else {
		ZVAL_LONG(&second, s->h);
	}
	return zend_compare(&first, &second);
}
/* }}} */

static zend_always_inline int php_array_key_compare_numeric_unstable_i(Bucket *f, Bucket *s) /* {{{ */
{
	if (f->key == NULL && s->key == NULL) {
		return (zend_long)f->h > (zend_long)s->h ? 1 : -1;
	} else {
		double d1, d2;
		if (f->key) {
			d1 = zend_strtod(f->key->val, NULL);
		} else {
			d1 = (double)(zend_long)f->h;
		}
		if (s->key) {
			d2 = zend_strtod(s->key->val, NULL);
		} else {
			d2 = (double)(zend_long)s->h;
		}
		return ZEND_THREEWAY_COMPARE(d1, d2);
	}
}
/* }}} */

static zend_always_inline int php_array_key_compare_string_case_unstable_i(Bucket *f, Bucket *s) /* {{{ */
{
	const char *s1, *s2;
	size_t l1, l2;
	char buf1[MAX_LENGTH_OF_LONG + 1];
	char buf2[MAX_LENGTH_OF_LONG + 1];

	if (f->key) {
		s1 = f->key->val;
		l1 = f->key->len;
	} else {
		s1 = zend_print_long_to_buf(buf1 + sizeof(buf1) - 1, f->h);
		l1 = buf1 + sizeof(buf1) - 1 - s1;
	}
	if (s->key) {
		s2 = s->key->val;
		l2 = s->key->len;
	} else {
		s2 = zend_print_long_to_buf(buf2 + sizeof(buf2) - 1, s->h);
		l2 = buf2 + sizeof(buf2) - 1 - s2;
	}
	return zend_binary_strcasecmp_l(s1, l1, s2, l2);
}
/* }}} */

static zend_always_inline int php_array_key_compare_string_unstable_i(Bucket *f, Bucket *s) /* {{{ */
{
	const char *s1, *s2;
	size_t l1, l2;
	char buf1[MAX_LENGTH_OF_LONG + 1];
	char buf2[MAX_LENGTH_OF_LONG + 1];

	if (f->key) {
		s1 = f->key->val;
