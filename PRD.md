# Product Requirements Document: Bookshelf

## 1. Meta Information
* **Project Name:** Bookshelf
* **Status:** Draft
* **Document Owner:** Me :)

## 2. Product Vision & Problem Statement
**Problem Statement:**
Avid digital readers and data archivists often struggle with fragmented ebook ecosystems. Managing massive, external database dumps alongside personal collections results in poor discovery, inconsistent metadata, and a disjointed reading experience. Existing solutions either lack automated synchronization with major external libraries or fail to provide a seamless, integrated environment for both cataloging and previewing content.

**Product Vision:**
Bookshelf is a unified digital library management system designed to seamlessly aggregate massive external ebook databases into a streamlined, OPDS-compatible platform. It aims to bridge the gap between large-scale data archiving and user-friendly daily reading by providing robust cataloging, granular access control, and built-in reading and previewing capabilities.

## 3. Target Audience
* **Digital Archivists / Self-Hosters:** Users who maintain large, localized copies of external book databases and need a robust engine to index, filter, and serve this data.
* **Avid Readers / Heavy Consumers:** Users who consume large volumes of literature and require advanced filtering, OPDS syndication for their e-ink devices, and an accessible web-preview system.

## 4. Scope & Milestones

**Phase 1: Initial Release (v1.0)**
* Basic cataloging and metadata display.
* OPDS interface implementation.
* Role-based user authentication (Guest, Basic, Privileged), including third-party authentication support (Google OAuth). 
* Basic search and filtering.
* Flibusta synchronization (DB dump parsing + targeted file import).
* Integrated Simple Web Reader (Text-only preview).

**Phase 2: Future Enhancements (v2.0)**
* Manual book upload capability.
* Subscriptions and background task processing (Celery) for notifications.
* Integrated Web Reader v2 (Image support).
* Format conversion (FB2 <-> EPUB).
* Automated audiobook generation (TTS processing).
* Data Migration: Seamless transition of the physical file archive from local storage to S3-compatible object storage, including URL resolution refactoring.

**Out of Scope**
* PDF and MOBI format support.
* Native mobile applications (iOS/Android).
* Payment gateways or monetization features.
* Full-text search (Elasticsearch or similar deep-content indexing).

## 5. Functional Requirements

### 5.1 Catalog & Discovery
* **Global Search:** Provide text search across Book Titles, Authors, and Series names.
  * Search results must support partial matching.
* **Recent Additions:** Display a dynamic list of the most recently added books.
* **Author Directory:** Provide an alphabetically sortable list of all authors.
* **Book Directory:** Provide a list of all books with multi-parameter filtering (Language, Genre, Alphabetical).

### 5.2 Entity Information Pages
* **Author Profile:**
  * Display all books associated with the author.
  * Sorting options: Alphabetical, Date added.
  * Grouping options: Group books by Series.
  * Filtering options: Filter author's works by Language and Genre.
* **Book Profile:**
  * Display metadata: Author(s), Series, Cover Image, and Annotation/Description.
  * Provide a secure download link (subject to user permissions).

### 5.3 Integrated Web Reader (Preview Engine)
* **Purpose:** Intended primarily for content preview to help users decide whether to download the file. It is not designed to replace standalone e-readers.
* **Features:**
  * Chapter-based navigation.
  * Raw text rendering (CSS is stripped or ignored).
  * *v2.0:* Inline illustration rendering.
* **Content Delivery & Caching Strategy:**
  * **On-the-fly Extraction:** The backend does not pre-parse books into the database. When a user requests to read a book, the backend dynamically parses the EPUB/FB2 file and extracts the requested chapter.
  * **Ephemeral Caching:** Extracted chapters are stored in a fast, in-memory cache (e.g., Redis) with a long Time-To-Live (TTL) of several hours. This ensures rapid sequential loading during an active reading session.
  * **Resource Management:** To prevent memory exhaustion during simultaneous parsing of large XML/FB2 files, the system must utilize streaming parsers and the cache must enforce a strict memory limit with an LRU (Least Recently Used) eviction policy.
  * **Access Restrictions:** For Basic Authenticated users, the extraction engine truncates the output, returning only the first few hundred words of the chapter. Privileged users receive the full chapter text.

### 5.4 User Features & Subscriptions
* **Reading List:** Users can save books to a personal "To Read" queue.
* **Favorites:** Users can mark Authors and Series as favorites.
* **Notifications (v2.0):** Users can subscribe to Authors/Series to receive alerts regarding new additions.
  * **In-App Notifications:** An expandable notification center located on the main dashboard, displaying a list of new releases with a "Clear/Dismiss" functionality to manage read status.
  * **Email Delivery:** Automated email daily digests sent to the user's registered email address via background workers.
  * **Third-Party Integration (TBD):** Potential future integration with messenger bots (e.g., Telegram) remains under consideration but is strictly out of scope for the initial v2.0 release.
* **Audiobook Generation (v2.0):** System capability to convert text files into audio formats.

### 5.5 OPDS Catalog Support
* **Public Discovery:** The core OPDS catalog structure (general Author indexes, Book lists, metadata, and cover images) is publicly accessible without authentication.
* **Personal Feeds (Protected):** The OPDS root navigation will include specific feeds for the user's "Reading List", "Favorite Authors", and "Favorite Series". Accessing these specific feed URLs is restricted and requires Basic Authentication.
* **Navigation:** Alphabetical indexing for both Authors and Books.
* **Author Feeds:** Books sorted by alphabetical order, date added, and grouped by series.
* **Protected Acquisition:** Download feeds (`<link rel="http://opds-spec.org/acquisition" ...>`) are strictly protected. Initiating a download requires Basic Authentication.
* **OAuth User Handling:** Users who registered via third-party providers (e.g., Google OAuth) must establish a local password in their web profile settings to utilize OPDS Basic Authentication. The web interface will prompt users to configure this upon their first login if they wish to use external e-readers.

### 5.6 External Synchronization & Metadata Resolution
* **Shadow Database (Metadata Resolver):** The system will maintain an isolated set of database tables containing the full Flibusta metadata dump. This data will *never* be exposed directly to end-users in the UI.
* **Purpose:** The shadow database acts purely as an internal, offline metadata provider during the book import process.
* **Import Workflow:** 
  1. The system scans local staging directories or daily update archives for new book files.
  2. The system cross-references the file identifiers with the shadow database.
  3. If the metadata matches the system's predefined filters (Language, Genre), the file is moved to primary storage, and a corresponding record is created in the main, user-facing library tables.

### 5.7 Role-Based Access Control (RBAC)
* **Guest (Unauthenticated):**
  * Full access to catalog browsing and metadata.
  * *Restricted:* Cannot use the Web Reader, download books (via Web or OPDS), use personal features (Reading List, Favorites, Notifications), or generate audiobooks.
* **Authenticated (Basic User) - [Default Role]:**
  * *Assignment:* This is the default role automatically assigned to all new user accounts upon successful registration (including third-party Google OAuth sign-ins).
  * *Granted:* Access to personal features (Reading List, Favorites, Notifications). Access to the Web Reader in "Preview Mode" (strictly limited to the first few hundred words of a chapter (under consideration, but no more than 500)).
  * *Restricted:* Cannot download full books (via Web or OPDS), access full text in the reader, or generate audiobooks.
* **Privileged User:**
  * *Granted:* Full access to all catalog features, full text in the Web Reader, and full download capabilities (Web and OPDS).
  * *Restricted:* Cannot generate audiobooks.
* **Beta-Tester Group:**
  * *Granted:* Exclusive access to the Audiobook Generation tools (in addition to standard Privileged rights).

### 5.8 Manual Book Upload & Metadata Extraction (v2.0)
* **Target Users:** Privileged Users and Administrators.
* **Workflow:**
  1. **File Upload:** The user selects and uploads an EPUB or FB2 file via the web interface.
  2. **Auto-Extraction (Pre-fill):** The backend system parses the file to automatically extract embedded metadata (Title, Author(s), Annotation/Description, Language, Genres, and Cover Image).
  3. **Review & Edit:** The extracted data is populated into an editable web form.
  4. **Manual Override:** The user reviews the pre-filled information, corrects any parsing errors, and manually adds missing data.
  5. **Finalization:** The user submits the form. The file is then moved to the permanent storage (S3) and the verified metadata is committed to the primary database.
* **Fault Tolerance:** The extraction parser must fail gracefully. If a file is malformed or lacks internal metadata, the system must not block the upload process; instead, it should present a blank form for completely manual entry.

### 5.9 Administration
* **Administration Interface:** Administrative operations are performed through the standard Django Admin interface. No custom administrative dashboard is planned.
* **Administrator Role:**
  * Administrators have unrestricted access to all system data and functionality.
  * Administrators can manage user accounts and assign or revoke system roles (Basic User, Privileged User, Beta Tester).
* **Catalog Management:**
  * Create, edit, and delete Author, Book, Series, and related metadata records.
  * Correct metadata inconsistencies resulting from automated imports or manual uploads.
  * Manage cover images, annotations, genres, languages, and other catalog attributes.
* **Import Oversight:**
  * Review imported records and resolve data quality issues.
  * Monitor synchronization and ingestion processes.
  * Access import logs and error reports generated during metadata resolution and file processing.
* **Content Management:**
  * Manage manually uploaded books and associated metadata.
  * Remove duplicate, invalid, or unwanted content from the catalog.
* **System Management:**
  * Manage system configuration required for synchronization, storage, and external service integrations.
  * Access operational information necessary for troubleshooting and maintenance.  
  
## 6. Non-Functional Requirements (NFRs)

### 6.1 Performance & Scalability
* **Search Performance:** Text search across Series, Authors and Book Titles must execute in under 300ms, even with a dataset exceeding 500,000 records. 
* **Database Optimization:** To achieve this without external search engines, the primary PostgreSQL database must utilize native text-search optimizations (e.g., GIN indexes with `pg_trgm` for trigram matching) on frequently queried text columns. Unindexed `ILIKE` operations are strictly prohibited for core catalog searches.
* **Background Processing:** Intensive operations (metadata ingestion, bulk imports) must run asynchronously and must not lock database tables required for front-end read operations.

### 6.2 Security & Access
* **Endpoint Protection & OPDS Auth:** All web download routes must validate user authorization levels.
  * *Public OPDS:* General catalog browsing is unauthenticated.
  * *Protected OPDS:* Requests to acquisition (download) endpoints AND personal feed endpoints (Reading List, Favorites) must return a standard HTTP 401 Unauthorized challenge.
* **Rate Limiting:** All OPDS endpoints and file acquisition routes must implement robust rate limiting. This is required to prevent automated scraping, denial-of-service events, and excessive bandwidth consumption. Specific thresholds and burst limits will be configured dynamically based on available server capacity.
* **Microservice Authentication:** Communication between the main web application and the external Audiobook Generation microservice must be secured (e.g., via internal network/VPC, mutual TLS, or shared secret tokens).

### 6.3 Usability & UX
* **Progressive Enhancement:** The web interface should function without complex JavaScript where possible (relying on HTMX for dynamic updates), ensuring broad compatibility across standard web browsers and e-ink browser engines.

### 6.4 Storage Strategy & Data Management
* **Phase 1 (v1.0): Local File System.**
  * All parsed and approved electronic book files will be stored directly on the application server's local file system.
  * The system will maintain a strict directory structure separating staging areas (for incoming Flibusta daily updates) from the active, user-accessible library directory.
  * *Technical Constraint:* Backups and storage scaling will rely on server-level volume snapshots or file-level synchronization (e.g., rsync).
* **Phase 2 (v2.0): S3-Compatible Object Storage.**
  * Migration of all physical file storage to an S3-compatible cloud or self-hosted solution (e.g., MinIO, AWS S3, DigitalOcean Spaces).
  * The database will transition from storing absolute local file paths to storing S3 object keys.
  * File delivery will be handled via securely generated presigned URLs to offload bandwidth from the main application server.

## 7. System Architecture & Technical Constraints

### 7.1 Tech Stack
* **Backend:** Python, Django, Django REST Framework (DRF).
* **Database:** PostgreSQL (handling both user-facing library data and the isolated shadow metadata tables).
* **Frontend:** HTML templates, HTMX (for asynchronous UI updates), Bootstrap (for responsive layout).
* **Asynchronous Tasks:** Celery + Redis (Message Broker).

### 7.2 Microservice Architecture (v2.0)
* **Audiobook Generator Node:** The TTS (Text-to-Speech) conversion engine will be isolated into a standalone microservice hosted on a separate physical/virtual server.
* **Communication:** Tasks will be pushed to the remote worker via the message broker. The microservice will push the generated audio files back to the main server's storage upon completion via a secure callback API.

### 7.3 External Services & Integrations
* **Email Service (v2.0):** Integration with an external SMTP provider (or a local SMTP relay) to dispatch transactional emails and notification digests. The actual dispatch process must be handled asynchronously via Celery.

### 7.4 Deployment & Infrastructure
* **Containerization:** The entire application ecosystem (Django backend, PostgreSQL database, Redis broker, and Celery workers) must be fully containerized using Docker and orchestrated via Docker Compose to ensure consistent environments across development and production.
* **Web Server & Reverse Proxy:** Nginx will be utilized as the primary entry point (Reverse Proxy), handling incoming HTTP/HTTPS traffic and routing requests to the appropriate application containers.
* **Static & Media Files (Phase 1):** Prior to the Phase 2 migration to S3-compatible storage, Nginx will be strictly responsible for the highly efficient, direct serving of all static assets and user-uploaded media (including EPUB/FB2 files and cover images), bypassing the Python application server entirely.
* **Hardware Requirements:** Specific physical infrastructure constraints (CPU cores, RAM, Disk IOPS) are kept generic and scalable. However, the host machine must be provisioned with sufficient memory to support efficient PostgreSQL indexing for 500,000+ records and concurrent in-memory XML parsing by the background workers.
