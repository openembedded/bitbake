
test: bitbakec.so
	python test.py

bitbakescanner.cc: bitbakescanner.l
	flex -t bitbakescanner.l > bitbakescanner.cc

bitbakeparser.cc: bitbakeparser.y python_output.h 
	lemon bitbakeparser.y
	mv bitbakeparser.c bitbakeparser.cc

bitbakec.c: bitbakec.pyx
	pyrexc bitbakec.pyx

bitbakec-processed.c: bitbakec.c
	cat bitbakec.c | sed -e"s/__pyx_f_8bitbakec_//" > bitbakec-processed.c

bitbakec.o: bitbakec-processed.c
	gcc -c bitbakec-processed.c -o bitbakec.o -fPIC -I/usr/include/python2.4

bitbakeparser.o: bitbakeparser.cc 
	g++ -c bitbakeparser.cc -fPIC -I/usr/include/python2.4

bitbakescanner.o: bitbakescanner.cc
	g++ -c bitbakescanner.cc -fPIC -I/usr/include/python2.4

bitbakec.so: bitbakec.o bitbakeparser.o bitbakescanner.o
	g++ -shared -fPIC bitbakeparser.o bitbakescanner.o bitbakec.o -o bitbakec.so

clean:
	rm *.out
	rm *.cc
	rm bitbakec.c
	rm bitbakec-processed.c
	rm *.o
	rm *.so
