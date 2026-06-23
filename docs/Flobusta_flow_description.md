Logging strategy for the project:
- All messages must be written to the console.
    - Warning messages should be displayed in yellow (if possible).
	- Error messages should be displayed in red (if possible).
- Error messages must be emailed to EMAIL_HOST_USER.
- For the flibusta app all messages must be written to the update.log file as well.


Library update from Flibusta

Load books from Flibusta archives and Flibusta daily updates. Load books only for certain genres, languages, and formats.

The flow:

Update Flibusta tables from the Flibusta SQL dump.

a. Download book archives from flibusta.is/daily
b. Or get book archives from a given path.

A book archive is a ZIP file containing book files. The book files are named book_id.ext, where ext is a file extension (txt, pdf, epub, fb2, etc.). 
A book file might be zipped; in this case, it is named book_id.ext.zip.

For each file in the archive, do the following:

Find the book_id in libbook. If it is not found, skip the file and log a warning.

Get the book genres, language, and type (from the file extension). Compare the retrieved parameters with the filter. Skip the file if it does not pass the filter.

At this point, we have a list of book_ids planned for import.

For each book_id, start the following transaction:

Get the book authors from the libavtorname table. If a book author has a main_id field, use the main author instead.

Get or create corresponding authors in the library app. (We need to design a mechanism to link an author from the library app with an author from Flibusta.)

Get book genres, series, and language.

Get or create corresponding genres, series, and language in the library app. (We need to design a mechanism to link them as well.)

Get book metadata from the file.

Create a book entry in the library app.

Link imported book with the book entry in the libbook table. (We need to design a mechanism to link them as well.)
