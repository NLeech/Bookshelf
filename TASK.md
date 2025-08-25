Develop a web application — an online library for storing, cataloging, and providing access to electronic books in EPUB format.

---

## Core Functionality

- **EPUB Book Management**  
  Store and organize electronic books in EPUB format.

- **User Authentication**  
  - Only authenticated users can view and download book content.  
  - Only authenticated users have access to personal features like download history and reading lists.
  - All other features are accessible without authentication.

- **Download History**  
  Each user can view a personal history of downloaded books.

- **Reading List**  
  Users can create a personalized list of books they plan to read.

- **OPDS Interface Support**  
  Enables integration with external applications and e-readers.

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
Frontend: Bootstrap (Webpack, Vue - optional, not at the first stage)
Server: Nginx
