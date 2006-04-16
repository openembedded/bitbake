
#ifndef LEXERC_H
#define LEXERC_H

#include <stdio.h>

extern int lineError;
extern int errorParse;

typedef struct {
    void *parser;
    void *scanner;
    FILE *file;
    PyObject *data;
} lex_t;

#endif
