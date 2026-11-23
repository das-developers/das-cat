# A Das2 Federated Catalog Browser

This is a single file Python 3 CGI script that can be dropped on a web server
to provide a das2 catalog browser.  It is a single source file implementation
and doesn't depend on das2C, das2py or any other das2-specific libraries, or
on anything outside the Python standard library.  It does reference the
following external files:

   resource/das2logo_rv.png
	resource/eyecandy.png   (assumed to be in same dir a sytle sheet)
	resource/style.css

Which are assumed to be at http(s)://das2.org/cat_resource, but this can be
changed by editing global variables at top of the CGI script.  The catalog
root files it starts from are set there as well.

It reads Catalog 0.5, SourceSet 0.2 and HttpStreamSrc 0.7 nodes.  Source
nodes in the layout used before 0.7 are listed but get no download form.

## How a download works

A source page is a plain HTML form, no javascript.  The form is sent back to
the script, which works out the request URL from the node and the settings
and answers with a redirect to the data server.  "Show URL" prints the URLs
instead.  Problems with the settings are listed on the page.

An example on a source page is a link that fills in the form.

The rules for turning settings into a URL are in `doc/httpstreamsrc.md`, and
das2C is the program that defines them.  The script carries its own copy of
that logic so that it can stand alone.  Check the copy against das2C after
changing either:

    test/browse_url_check.py TREE     (needs das_fetch from das2C)

A node given to the resolve box by its URL, and not reached by a catalog
path, gets "Show URL" only.  The script does not redirect browsers to
wherever such a file says.
