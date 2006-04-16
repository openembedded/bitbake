#ifndef PYTHON_OUTPUT_H
#define PYTHON_OUTPUT_H
/*
Copyright (C) 2006 Holger Hans Peter Freyther

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR
THE USE OR OTHER DEALINGS IN THE SOFTWARE.

This is the glue:
    It will be called from the lemon grammar and will call into
    python to set certain things.

*/

extern "C" {

struct lex_t;

extern void e_assign(lex_t*, const char*, const char*);
extern void e_export(lex_t*, const char*);
extern void e_immediate(lex_t*, const char*, const char*);
extern void e_cond(lex_t*, const char*, const char*);
extern void e_prepend(lex_t*, const char*, const char*);
extern void e_append(lex_t*, const char*, const char*);
extern void e_precat(lex_t*, const char*, const char*);
extern void e_postcat(lex_t*, const char*, const char*);

extern void e_addtask(lex_t*, const char*, const char*, const char*);
extern void e_addhandler(lex_t*,const char*);
extern void e_export_func(lex_t*, const char*);
extern void e_inherit(lex_t*, const char*);
extern void e_include(lex_t*, const char*);
extern void e_require(lex_t*, const char*);
extern void e_proc(lex_t*, const char*, const char*);
extern void e_proc_python(lex_t*, const char*, const char*);
extern void e_proc_fakeroot(lex_t*, const char*, const char*);
extern void e_def(lex_t*, const char*, const char*, const char*);
extern void e_parse_error(lex_t*);

}
#endif // PYTHON_OUTPUT_H
