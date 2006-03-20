/*
Copyright (C) 2005 Holger Hans Peter Freyther

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

*/

#ifndef TOKEN_H
#define TOKEN_H

#include <ctype.h>
#include <string.h>

#define PURE_METHOD


/**
 * Special Value for End Of File Handling. We set it to
 * 1001 so we can have up to 1000 Terminal Symbols on
 * grammar. Currenlty we have around 20
 */
#define T_EOF    1001

struct token_t {
    const char* string()const PURE_METHOD;

    static char* concatString(const char* l, const char* r);
    void assignString(char* str);
    void copyString(const char* str);

    void release_this();

private:
    char  *m_string;
    size_t m_stringLen;
};

inline const char* token_t::string()const
{
    return m_string;
}

/*
 * append str to the current string
 */
inline char* token_t::concatString(const char* l, const char* r)
{
    size_t cb = (l ? strlen (l) : 0) + strlen (r) + 1;
    char *r_sz = new char[cb];
    *r_sz = 0;

    if (l)
        strcat (r_sz, l);
    strcat (r_sz, r);

    return r_sz;
}

inline void token_t::assignString(char* str)
{
    m_string = str;
    m_stringLen = str ? strlen(str) : 0;
}

inline void token_t::copyString(const char* str)
{
    if( str ) {
        m_stringLen = strlen(str);
        m_string = new char[m_stringLen+1];
        strcpy(m_string, str);
    }
}

inline void token_t::release_this()
{
    delete m_string;
    m_string = 0;
}

#endif
