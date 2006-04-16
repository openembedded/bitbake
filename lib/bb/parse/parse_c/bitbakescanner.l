/* bbf.flex 

   written by Marc Singer
   6 January 2005

   This program is free software; you can redistribute it and/or
   modify it under the terms of the GNU General Public License as
   published by the Free Software Foundation; either version 2 of the
   License, or (at your option) any later version.

   This program is distributed in the hope that it will be useful, but
   WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
   General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program; if not, write to the Free Software
   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
   USA.

   DESCRIPTION
   -----------

   flex lexer specification for a BitBake input file parser.

   Unfortunately, flex doesn't welcome comments within the rule sets.
   I say unfortunately because this lexer is unreasonably complex and
   comments would make the code much easier to comprehend.

   The BitBake grammar is not regular.  In order to interpret all
   of the available input files, the lexer maintains much state as it
   parses.  There are places where this lexer will emit tokens that
   are invalid.  The parser will tend to catch these. 

   The lexer requires C++ at the moment.  The only reason for this has
   to do with a very small amount of managed state.  Producing a C
   lexer should be a reasonably easy task as long as the %reentrant
   option is used.


   NOTES
   -----

   o RVALUES.  There are three kinds of RVALUES.  There are unquoted
     values, double quote enclosed strings, and single quote 
     strings.  Quoted strings may contain unescaped quotes (of either
     type), *and* any type may span more than one line by using a
     continuation '\' at the end of the line.  This requires us to
     recognize all types of values with a single expression.
     Moreover, the only reason to quote a value is to include
     trailing or leading whitespace.  Whitespace within a value is
     preserved, ugh.

   o CLASSES.  C_ patterns define classes.  Classes ought not include
     a repitition operator, instead letting the reference to the class
     define the repitition count.

     C_SS - symbol start
     C_SB - symbol body
     C_SP - whitespace

*/

%option never-interactive
%option yylineno
%option noyywrap
%option reentrant stack


%{

#include "token.h"
#include "lexer.h"
#include "bitbakeparser.h"
#include <ctype.h>

extern void *bbparseAlloc(void *(*mallocProc)(size_t));
extern void bbparseFree(void *p, void (*freeProc)(void*));
extern void *bbparseAlloc(void *(*mallocProc)(size_t));
extern void *bbparse(void*, int, token_t, lex_t*);
extern void bbparseTrace(FILE *TraceFILE, char *zTracePrompt);

//static const char* rgbInput;
//static size_t cbInput;

extern "C" {

int lineError;
int errorParse;

enum {
  errorNone = 0,
  errorUnexpectedInput,
  errorUnsupportedFeature, 
};

}

#define YY_EXTRA_TYPE lex_t*

	/* Read from buffer */
#define YY_INPUT(buf,result,max_size) \
 { yyextra->input(buf, &result, max_size); }

//#define YY_DECL static size_t yylex ()

#define ERROR(e) \
  do { lineError = yylineno; errorParse = e; yyterminate (); } while (0)

static const char* fixup_escapes (const char* sz);

%}


C_SP            [ \t]
COMMENT         #.*\n
OP_ASSIGN       "="
OP_PREDOT       ".="
OP_POSTDOT      "=."
OP_IMMEDIATE    ":="
OP_PREPEND      "=+"
OP_APPEND       "+="
OP_COND         "?="
B_OPEN          "{"
B_CLOSE         "}"

K_ADDTASK       "addtask"
K_ADDHANDLER    "addhandler"
K_AFTER         "after"
K_BEFORE        "before"
K_DEF           "def"
K_INCLUDE       "include"
K_REQUIRE       "require"
K_INHERIT       "inherit"
K_PYTHON        "python"
K_FAKEROOT      "fakeroot"
K_EXPORT        "export"
K_EXPORT_FUNC   "EXPORT_FUNCTIONS"

STRING          \"([^\n\r]|"\\\n")*\"
SSTRING         \'([^\n\r]|"\\\n")*\'
VALUE           ([^'" \t\n])|([^'" \t\n]([^\n]|(\\\n))*[^'" \t\n])

C_SS            [a-zA-Z_]
C_SB            [a-zA-Z0-9_+-.]
REF             $\{{C_SS}{C_SB}*\}
SYMBOL          {C_SS}{C_SB}*
VARIABLE        $?{C_SS}({C_SB}*|{REF})*(\[[a-zA-Z0-9_]*\])?
FILENAME        ([a-zA-Z_./]|{REF})(([-+a-zA-Z0-9_./]*)|{REF})*

PROC            \({C_SP}*\)

%s S_DEF
%s S_DEF_ARGS
%s S_DEF_BODY
%s S_FUNC
%s S_INCLUDE
%s S_INHERIT
%s S_REQUIRE
%s S_PROC
%s S_RVALUE
%s S_TASK

%%

{OP_APPEND}                     { BEGIN S_RVALUE;
                                  yyextra->accept (T_OP_APPEND); }
{OP_PREPEND}                    { BEGIN S_RVALUE;
                                  yyextra->accept (T_OP_PREPEND); }
{OP_IMMEDIATE}                  { BEGIN S_RVALUE;
                                  yyextra->accept (T_OP_IMMEDIATE); }
{OP_ASSIGN}                     { BEGIN S_RVALUE;
                                  yyextra->accept (T_OP_ASSIGN); }
{OP_PREDOT}                     { BEGIN S_RVALUE;
                                  yyextra->accept (T_OP_PREDOT); }
{OP_POSTDOT}                    { BEGIN S_RVALUE;
                                  yyextra->accept (T_OP_POSTDOT); }
{OP_COND}                       { BEGIN S_RVALUE;
                                  yyextra->accept (T_OP_COND); }

<S_RVALUE>\\\n{C_SP}*           {  }
<S_RVALUE>{STRING}              { BEGIN INITIAL;
                                  size_t cb = yyleng;
                                  while (cb && isspace (yytext[cb - 1]))
                                      --cb;
                                  yytext[cb - 1] = 0;
                                  yyextra->accept (T_STRING, yytext + 1); }
<S_RVALUE>{SSTRING}             { BEGIN INITIAL;
                                  size_t cb = yyleng;
                                  while (cb && isspace (yytext[cb - 1]))
                                      --cb;
                                  yytext[cb - 1] = 0;
                                  yyextra->accept (T_STRING, yytext + 1); }

<S_RVALUE>{VALUE}               { ERROR (errorUnexpectedInput);  }
<S_RVALUE>{C_SP}*\n+            { BEGIN INITIAL;
                                  yyextra->accept (T_STRING, NULL); }

{K_INCLUDE}                     { BEGIN S_INCLUDE;
                                  yyextra->accept (T_INCLUDE); }
{K_REQUIRE}                     { BEGIN S_REQUIRE;
                                  yyextra->accept (T_REQUIRE); }
{K_INHERIT}                     { BEGIN S_INHERIT;
                                  yyextra->accept (T_INHERIT); }
{K_ADDTASK}                     { BEGIN S_TASK;
                                  yyextra->accept (T_ADDTASK); }
{K_ADDHANDLER}                  { yyextra->accept (T_ADDHANDLER); }
{K_EXPORT_FUNC}                 { BEGIN S_FUNC;
                                  yyextra->accept (T_EXPORT_FUNC); }
<S_TASK>{K_BEFORE}              { yyextra->accept (T_BEFORE); }
<S_TASK>{K_AFTER}               { yyextra->accept (T_AFTER); }
<INITIAL>{K_EXPORT}             { yyextra->accept (T_EXPORT); }

<INITIAL>{K_FAKEROOT}           { yyextra->accept (T_FAKEROOT); }
<INITIAL>{K_PYTHON}             { yyextra->accept (T_PYTHON); }
{PROC}{C_SP}*{B_OPEN}{C_SP}*\n*  { BEGIN S_PROC;
                                  yyextra->accept (T_PROC_OPEN); }
<S_PROC>{B_CLOSE}{C_SP}*\n*      { BEGIN INITIAL;
                                  yyextra->accept (T_PROC_CLOSE); }
<S_PROC>([^}][^\n]*)?\n*        { yyextra->accept (T_PROC_BODY, yytext); }

{K_DEF}                         { BEGIN S_DEF; }
<S_DEF>{SYMBOL}                 { BEGIN S_DEF_ARGS;
                                  yyextra->accept (T_SYMBOL, yytext); }
<S_DEF_ARGS>[^\n:]*:            { yyextra->accept (T_DEF_ARGS, yytext); }
<S_DEF_ARGS>{C_SP}*\n           { BEGIN S_DEF_BODY; }
<S_DEF_BODY>{C_SP}+[^\n]*\n     { yyextra->accept (T_DEF_BODY, yytext); }
<S_DEF_BODY>\n                  { yyextra->accept (T_DEF_BODY, yytext); }
<S_DEF_BODY>.                   { BEGIN INITIAL; unput (yytext[0]); }

{COMMENT}                       { }

<INITIAL>{SYMBOL}               { yyextra->accept (T_SYMBOL, yytext); }
<INITIAL>{VARIABLE}             { yyextra->accept (T_VARIABLE, yytext); }

<S_TASK>{SYMBOL}                { yyextra->accept (T_TSYMBOL, yytext); }
<S_FUNC>{SYMBOL}                { yyextra->accept (T_FSYMBOL, yytext); }
<S_INHERIT>{SYMBOL}             { yyextra->accept (T_ISYMBOL, yytext); }
<S_INCLUDE>{FILENAME}           { BEGIN INITIAL;
                                  yyextra->accept (T_ISYMBOL, yytext); }
<S_REQUIRE>{FILENAME}           { BEGIN INITIAL;
                                  yyextra->accept (T_ISYMBOL, yytext); }
<S_TASK>\n                      { BEGIN INITIAL; }
<S_FUNC>\n                      { BEGIN INITIAL; }
<S_INHERIT>\n                   { BEGIN INITIAL; }

[ \t\r\n]                       /* Insignificant whitespace */

.                               { ERROR (errorUnexpectedInput); }

                                /* Check for premature termination */
<<EOF>>                         { return T_EOF; }

%%

void lex_t::accept (int token, const char* sz) 
{
    token_t t;
    memset (&t, 0, sizeof (t));
    t.copyString(sz);

    /* tell lemon to parse the token */
    parse (parser, token, t, this);
}

void lex_t::input (char *buf, int *result, int max_size)
{
    printf("lex_t::input %p %d\n", buf, max_size);
    *result = fread(buf, 1, max_size, file);
    printf("lex_t::input result %d\n", *result);
}

int lex_t::line ()const
{
    printf("lex_t::line\n");
    return yyget_lineno (scanner);
}


extern "C" {

    void parse (FILE* file, PyObject* data)
    {
	printf("parse bbparseAlloc\n");
        void* parser = bbparseAlloc (malloc);
        yyscan_t scanner;
        lex_t lex;

	printf("parse yylex_init\n");
        yylex_init (&scanner);

        lex.parser = parser;
        lex.scanner = scanner;
        lex.file = file;
        lex.data = data;
        lex.parse = bbparse;
	printf("parse yyset_extra\n");
        yyset_extra (&lex, scanner);

	printf("parse yylex\n");
        int result = yylex (scanner);
	
	printf("parse result %d\n", result);

        lex.accept (0);
	printf("parse lex.accept\n");
        bbparseTrace (NULL, NULL);
	printf("parse bbparseTrace\n");

        if (result != T_EOF)
           printf ("premature end of file\n");

        yylex_destroy (scanner);
        bbparseFree (parser, free);
    }

}
