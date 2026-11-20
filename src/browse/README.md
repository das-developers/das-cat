# A Das2 Federated Catalog Browser

This is a single file Python 3 CGI script that can be dropped on a web server
to provide a das2 catalog browser.  It is a single source file implementation
and doesn't depend on libdas2, dasCore or any other das2-specific libraries, 
though it does reference the following external files:

   resource/das2logo_rv.png
	resource/eyecandy.png   (assumed to be in same dir a sytle sheet)
	resource/style.css

Which are assumed to be at http(s)://das2.org/cat_resource, but this can be
changed by editing global variables at top of the CGI script.

