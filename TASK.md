Develop a web application — an online library for storing, cataloging, and providing access to electronic books in EPUB and FB2 format.

---

## Core Functionality

- **EPUB and FB2 Book Management**  
  Store and organize electronic books in EPUB and FB2 formats.

- **Book Metadata**  
  Store and display metadata such as title, author(s), description, cover image, language, and ISBN.
 
- **Search and Filtering**  
  Allow users to search for books by title, author, genre, and other metadata fields.

- **Synchronisation**
  - Mirror of the Flibusta library database (see Flibusta.md).
  - Initial import of books and subsequent synchronization with the Flibusta library (only for selected genres and languages).

- **User Authentication**  
  - Only authenticated users can view and download book content.  
  - Only authenticated users have access to personal features described below:
  - All other features are accessible without authentication.

- **Download history**  
  Each user can view a personal history of downloaded books.

- **Reading List**  
  Users can create a personalized list of books they plan to read.

- **Favorite Authors**
  - Users can mark authors as favorites for easy access to their works.
  - Users can subscribe to authors to receive notifications about new books.

- **OPDS Interface Support**  
  Enables integration with external applications and e-readers.
  
- **Integrated book reader**  
  Provide an online reader for EPUB and FB2 formats, allowing users to read books directly in the browser.

---

## Key Entities

### Language  
Represents the language of books, authors, genres, and other elements.

### Genre  
- Hierarchical structure: genres may contain subgenres.  
- Can have alternative names and translations into other languages.

### Author  
- May have pseudonyms and name translations into other languages.  
- Can be associated with multiple books.

### Book Series  
- Hierarchical structure: series may include subseries.  
- Can have alternative names and translations into other languages.

### Book  
- **Required fields**: title and at least one author.  
- **Optional fields**: description, language, cover image, ISBN.  
- May belong to multiple authors, genres, and series.

## Stack:
Framework: Django, DRF  
Database: PostgreSQL
Virtualization: Docker
Background Task Queue: Celery
Broker: Redis
Frontend: Bootstrap, HTMX (Webpack, Vue or React - optional, not at the first stage)
Server: Nginx
