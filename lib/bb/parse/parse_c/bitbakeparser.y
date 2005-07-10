/* bbp.lemon 

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

   lemon parser specification file for a BitBake input file parser.

   Most of the interesting shenanigans are done in the lexer.  The
   BitBake grammar is not regular.  In order to emit tokens that
   the parser can properly interpret in LALR fashion, the lexer
   manages the interpretation state.  This is why there are ISYMBOLs,
   SYMBOLS, and TSYMBOLS.

   This parser was developed by reading the limited available
   documentation for BitBake and by analyzing the available BB files.
   There is no assertion of correctness to be made about this parser.

*/

%token_type {token_t}
%name bbparse
%token_prefix	T_
%extra_argument  {lex_t* lex}

%include {
#include <iostream>
#include "standard.h"
}


%token_destructor { $$.release_this (); }

%syntax_error     { printf ("%s:%d: syntax error\n",
                    lex->filename (), lex->line ()); }

program ::= statements.

statements ::= statements statement.
statements ::= .

variable(r) ::= SYMBOL(s).
        { r.sz = s.sz; s.sz = NULL;
          s.release_this (); }
variable(r) ::= VARIABLE(v).
        { char* sz = e_interpolate (v.sz);
          if (sz) { r.sz = sz; delete v.sz; }
          else    { r.sz = v.sz; }
          v.sz = NULL;
          v.release_this (); }

statement ::= EXPORT variable(s) OP_ASSIGN STRING(v).
        { e_assign (s.sz, v.sz); e_export (s.sz);
          s.release_this (); v.release_this (); }
statement ::= EXPORT variable(s) OP_IMMEDIATE STRING(v).
        { e_immediate (s.sz, v.sz); e_export (s.sz);
          s.release_this (); v.release_this (); }

statement ::= EXPORT variable(s) OP_COND STRING(v).
        { e_cond (s.sz, v.sz); e_export (s.sz);
          s.release_this (); v.release_this (); }

statement ::= variable(s) OP_ASSIGN STRING(v).
        { e_assign (s.sz, v.sz);
          s.release_this (); v.release_this (); }
statement ::= variable(s) OP_PREPEND STRING(v).
        { e_prepend (s.sz, v.sz);
          s.release_this (); v.release_this (); }
statement ::= variable(s) OP_APPEND STRING(v).
        { e_append (s.sz, v.sz);
          s.release_this (); v.release_this (); }
statement ::= variable(s) OP_IMMEDIATE STRING(v).
        { e_immediate (s.sz, v.sz);
          s.release_this (); v.release_this (); }
statement ::= variable(s) OP_COND STRING(v).
        { e_cond (s.sz, v.sz);
          s.release_this (); v.release_this (); }

task ::= TSYMBOL(t) BEFORE TSYMBOL(b) AFTER  TSYMBOL(a).
        { e_addtask (t.sz, b.sz, a.sz);
          t.release_this (); b.release_this (); a.release_this (); }
task ::= TSYMBOL(t) AFTER  TSYMBOL(a) BEFORE TSYMBOL(b).
        { e_addtask (t.sz, b.sz, a.sz);
          t.release_this (); a.release_this (); b.release_this (); }
task ::= TSYMBOL(t).
        { e_addtask (t.sz, NULL, NULL); 
          t.release_this ();}
task ::= TSYMBOL(t) BEFORE TSYMBOL(b).
        { e_addtask (t.sz, b.sz, NULL);
          t.release_this (); b.release_this (); }
task ::= TSYMBOL(t) AFTER  TSYMBOL(a).
        { e_addtask (t.sz, NULL, a.sz); 
          t.release_this (); a.release_this (); }
tasks ::= tasks task.
tasks ::= task.
statement ::= ADDTASK tasks.

statement ::= ADDHANDLER SYMBOL(s).
        { e_addhandler (s.sz); s.release_this (); }

func ::= FSYMBOL(f). { e_export_func (f.sz); f.release_this (); }
funcs ::= funcs func.
funcs ::= func.
statement ::= EXPORT_FUNC funcs.

inherit ::= ISYMBOL(i). { e_inherit (i.sz); i.release_this (); }
inherits ::= inherits inherit.
inherits ::= inherit.
statement ::= INHERIT inherits.

statement ::= INCLUDE ISYMBOL(i).
        { e_include (i.sz); i.release_this (); }

proc_body(r) ::= proc_body(l) PROC_BODY(b). 
        { /* concatenate body lines */
          size_t cb = (l.sz ? strlen (l.sz) : 0) + strlen (b.sz) + 1;
          r.sz = new char[cb];
          *r.sz = 0;
          if (l.sz) strcat (r.sz, l.sz);
          strcat (r.sz, b.sz);
          l.release_this ();
          b.release_this ();
        }
proc_body(b) ::= . { b.sz = 0; }
statement ::= variable(p) PROC_OPEN proc_body(b) PROC_CLOSE.
        { e_proc (p.sz, b.sz); 
          p.release_this (); b.release_this (); }
statement ::= PYTHON SYMBOL(p) PROC_OPEN proc_body(b) PROC_CLOSE.
        { e_proc_python (p.sz, b.sz); 
          p.release_this (); b.release_this (); }
statement ::= PYTHON PROC_OPEN proc_body(b) PROC_CLOSE.
        { e_proc_python (NULL, b.sz);
          b.release_this (); }

statement ::= FAKEROOT SYMBOL(p) PROC_OPEN proc_body(b) PROC_CLOSE.
        { e_proc_fakeroot (p.sz, b.sz);
          p.release_this (); b.release_this (); }

def_body(r) ::= def_body(l) DEF_BODY(b).
        { /* concatenate body lines */
          size_t cb = (l.sz ? strlen (l.sz) : 0) + strlen (b.sz);
          r.sz = new char[cb + 1];
          *r.sz = 0;
          if (l.sz) strcat (r.sz, l.sz);
          strcat (r.sz, b.sz); 
          l.release_this (); b.release_this ();
        }
def_body(b) ::= . { b.sz = 0; }
statement ::= SYMBOL(p) DEF_ARGS(a) def_body(b).
        { e_def (p.sz, a.sz, b.sz);
          p.release_this(); a.release_this (); b.release_this (); }
