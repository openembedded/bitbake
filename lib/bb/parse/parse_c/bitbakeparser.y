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
%token_prefix   T_
%extra_argument  {lex_t* lex}

%include {
#include "token.h"
#include "lexer.h"
#include "python_output.h"
}


%token_destructor { $$.release_this (); }

%syntax_error     { e_parse_error( lex ); }

program ::= statements.

statements ::= statements statement.
statements ::= .

variable(r) ::= SYMBOL(s).
        { r.assignString( (char*)s.string() );
          s.assignString( 0 );
          s.release_this(); }
variable(r) ::= VARIABLE(v).
        {
          r.assignString( (char*)v.string() );
          v.assignString( 0 );
          v.release_this(); }

statement ::= EXPORT variable(s) OP_ASSIGN STRING(v).
        { e_assign( lex, s.string(), v.string() );
          e_export( lex, s.string() );
          s.release_this(); v.release_this(); }
statement ::= EXPORT variable(s) OP_PREDOT STRING(v).
        { e_precat( lex, s.string(), v.string() );
          e_export( lex, s.string() );
          s.release_this(); v.release_this(); }
statement ::= EXPORT variable(s) OP_POSTDOT STRING(v).
        { e_postcat( lex, s.string(), v.string() );
          e_export( lex, s.string() );
          s.release_this(); v.release_this(); }
statement ::= EXPORT variable(s) OP_IMMEDIATE STRING(v).
        { e_immediate ( lex, s.string(), v.string() );
          e_export( lex, s.string() );
          s.release_this(); v.release_this(); }
statement ::= EXPORT variable(s) OP_COND STRING(v).
        { e_cond( lex, s.string(), v.string() );
          s.release_this(); v.release_this(); }

statement ::= variable(s) OP_ASSIGN STRING(v).
        { e_assign( lex, s.string(), v.string() );
          s.release_this(); v.release_this(); }
statement ::= variable(s) OP_PREDOT STRING(v).
        { e_precat( lex, s.string(), v.string() );
          s.release_this(); v.release_this(); }
statement ::= variable(s) OP_POSTDOT STRING(v).
        { e_postcat( lex, s.string(), v.string() );
          s.release_this(); v.release_this(); }
statement ::= variable(s) OP_PREPEND STRING(v).
        { e_prepend( lex, s.string(), v.string() );
          s.release_this(); v.release_this(); }
statement ::= variable(s) OP_APPEND STRING(v).
        { e_append( lex, s.string() , v.string() );
          s.release_this(); v.release_this(); }
statement ::= variable(s) OP_IMMEDIATE STRING(v).
        { e_immediate( lex, s.string(), v.string() );
          s.release_this(); v.release_this(); }
statement ::= variable(s) OP_COND STRING(v).
        { e_cond( lex, s.string(), v.string() );
          s.release_this(); v.release_this(); }

task ::= TSYMBOL(t) BEFORE TSYMBOL(b) AFTER  TSYMBOL(a).
        { e_addtask( lex, t.string(), b.string(), a.string() );
          t.release_this(); b.release_this(); a.release_this(); }
task ::= TSYMBOL(t) AFTER  TSYMBOL(a) BEFORE TSYMBOL(b).
        { e_addtask( lex, t.string(), b.string(), a.string());
          t.release_this(); a.release_this(); b.release_this(); }
task ::= TSYMBOL(t).
        { e_addtask( lex, t.string(), NULL, NULL);
          t.release_this();}
task ::= TSYMBOL(t) BEFORE TSYMBOL(b).
        { e_addtask( lex, t.string(), b.string(), NULL);
          t.release_this(); b.release_this(); }
task ::= TSYMBOL(t) AFTER  TSYMBOL(a).
        { e_addtask( lex, t.string(), NULL, a.string());
          t.release_this(); a.release_this(); }
tasks ::= tasks task.
tasks ::= task.
statement ::= ADDTASK tasks.

statement ::= ADDHANDLER SYMBOL(s).
        { e_addhandler( lex, s.string()); s.release_this (); }

func ::= FSYMBOL(f). { e_export_func( lex, f.string()); f.release_this(); }
funcs ::= funcs func.
funcs ::= func.
statement ::= EXPORT_FUNC funcs.

inherit ::= ISYMBOL(i). { e_inherit( lex, i.string() ); i.release_this (); }
inherits ::= inherits inherit.
inherits ::= inherit.
statement ::= INHERIT inherits.

statement ::= INCLUDE ISYMBOL(i).
        { e_include( lex, i.string() ); i.release_this(); }

statement ::= REQUIRE ISYMBOL(i).
        { e_require( lex, i.string() ); i.release_this(); }

proc_body(r) ::= proc_body(l) PROC_BODY(b).
        { /* concatenate body lines */
          r.assignString( token_t::concatString(l.string(), b.string()) );
          l.release_this ();
          b.release_this ();
        }
proc_body(b) ::= . { b.assignString(0); }
statement ::= variable(p) PROC_OPEN proc_body(b) PROC_CLOSE.
        { e_proc( lex, p.string(), b.string() );
          p.release_this(); b.release_this(); }
statement ::= PYTHON SYMBOL(p) PROC_OPEN proc_body(b) PROC_CLOSE.
        { e_proc_python ( lex, p.string(), b.string() );
          p.release_this(); b.release_this(); }
statement ::= PYTHON PROC_OPEN proc_body(b) PROC_CLOSE.
        { e_proc_python( lex, NULL, b.string());
          b.release_this (); }

statement ::= FAKEROOT SYMBOL(p) PROC_OPEN proc_body(b) PROC_CLOSE.
        { e_proc_fakeroot( lex, p.string(), b.string() );
          p.release_this (); b.release_this (); }

def_body(r) ::= def_body(l) DEF_BODY(b).
        { /* concatenate body lines */
          r.assignString( token_t::concatString(l.string(), b.string()) );
          l.release_this (); b.release_this ();
        }
def_body(b) ::= . { b.assignString( 0 ); }
statement ::= SYMBOL(p) DEF_ARGS(a) def_body(b).
        { e_def( lex, p.string(), a.string(), b.string());
          p.release_this(); a.release_this(); b.release_this(); }

