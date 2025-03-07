# Scrape Automation and Token Estimator

This is a powerful **Streamlit-based application** designed for managing scraping workflows, token estimation, and file compression. It provides a structured approach to managing projects and subprojects, allowing users to scrape, process, and analyze data efficiently.

---

## **Features**

- **Dynamic Project and Subproject Management**:
  - Create, manage, and navigate projects and their subprojects.
  - View a structured tree of projects and subprojects in real-time.

- **Scraping Tools**:
  - **Link Scraper**: Extract links from websites using predefined or custom strategies.
  - **Custom Link Scraper**: Advanced scraping with custom selectors and strategies.
  - **PDF Scraper**: Download and process PDFs from scraped links.
  - **WARC Scraper**: Save web pages as WARC files for archival purposes.

- **Token Estimation**:
  - Count tokens in PDFs and WARC files, with optional CSS selector-based extraction.
  - Batch processing and recalculation capabilities.
  - Historical token count tracking.

- **File Compression and Management**:
  - Compress PDFs into `.zip` files and WARC files into `.warc.gz` files.
  - Centralized compressed file management with `0_compressed_all` directory.
  - Automatic file updates and synchronization.

- **Enhanced Dashboard**:
  - Comprehensive project-level and subproject-level statistics.
  - Real-time file tracking with timestamps and modification dates.
  - Detailed metrics including WARC and PDF file counts.
  - Token calculation progress monitoring.
  - Bulk operations for token recalculation and file management.

---

## **Installation**

### 1. Clone the Repository
First, create a local folder and clone the repository:
```bash
git clone https://github.com/Malikusfz/ez-scrape.git .
```
or
```bash
git clone https://github.com/Malikusfz/ez-scrape.git
cd ez-scrape
```

### 2. Set Up a Virtual Environment
Create and activate a virtual environment to ensure dependency isolation:
```bash
python -m venv .venv
```
And then activate the virtual environment
On macOS/Linux:
```bash
source .venv/bin/activate
```
Or on Windows:
```bash
.venv\Scripts\activate
```

### 3. Install Dependencies
Install all required dependencies from the requirements.txt file:

```bash
pip install -r requirements.txt
```

on Windows add:
```bash
playwright install
```

### 4. Run the Streamlit Application
Start the Streamlit app:

```bash
streamlit run main.py
```

---

## **Usage**

### 1. Starting the App
Once the app starts, you will see a sidebar for managing projects and subprojects, and several feature tabs to navigate through.

### 2. Managing Projects and Subprojects
Before using any other features, you must first create a project and its subprojects:

- Navigate to the sidebar under the Project Management section.
- Click the "Add New Project" button to unlock the input field.
- Enter the project name (e.g., kominfo) and click Save New Project.
- Cancel the input section by clicking Cancel New Project.
- Select the newly created project from the dropdown.

Once a project is selected:

- Click "Add New Subproject" to unlock the input field.
- Enter subproject names (e.g., news, regulations, information) one by one, saving each.
- Select a subproject using the dropdown.

### 3. Dashboard and File Management
The enhanced dashboard provides:
- Real-time statistics for all projects and subprojects
- File counts, token counts, and storage metrics
- Last modification timestamps for tracking changes
- Bulk operations:
  - **Token Recalculation**: Update token counts across all projects
  - **Compressed File Management**: Automatically collect and organize compressed files

### 4. Feature Tabs
Once a project and subproject are selected, you can access:
- **Link Scraper**: Basic link extraction
- **Custom Link Scraper**: Advanced scraping with custom selectors
- **PDF Scraper**: PDF download and processing
- **WARC Scraper**: Web page archival
- **Token Estimator**: Token counting and analysis
- **Compressor**: File compression with central management
- **Dashboard**: Project statistics and bulk operations

---

## **Example Workflow**

Here’s a sample workflow for scraping data from the Kominfo website:

1. **Create a Project**: Add `kominfo` as a project.
2. **Add Subprojects**:
   - Add `news`, `regulations`, and `information` as subprojects under `kominfo`.
3. **Use Link Scraper**:
   - Scrape links from the news section of the Kominfo website.
   - Save the extracted links to `output/kominfo/news/links/links.csv`.
4. **Scrape PDFs and WARCs**:
   - Download PDFs from the scraped links into `output/kominfo/news/pdfs/scraped-pdfs/`.
   - Save web pages as `.warc` files into `output/kominfo/news/warcs/scraped-warcs/`.
5. **Estimate Tokens**:
   - Count tokens in the PDFs and WARCs for the news subproject.
6. **Compress Files**:
   - Compress the PDFs and WARCs for storage optimization.

---

## **Folder Structure**

The application creates and maintains the following structure:
```
output/
└── <project_name>/
    ├── 0_compressed_all/          # Centralized compressed file storage
    └── <subproject_name>/
        ├── pdfs/
        │   └── scraped-pdfs/
        ├── links/
        ├── warcs/
        │   └── scraped-warcs/
        ├── tokens/
        └── compressed/            # Subproject-level compressed files
```

- `0_compressed_all/`: Central storage for all compressed files in a project
- `pdfs/scraped-pdfs/`: Downloaded PDFs
- `links/`: Scraped links in CSV format
- `warcs/scraped-warcs/`: Archived web pages
- `tokens/`: Token count data
- `compressed/`: Subproject-specific compressed files

---

## **System Requirements**

- **Python**: Version 3.8 or later
- **Google Chrome**: Installed
- **ChromeDriver**: Compatible with your Chrome version

[Download ChromeDriver](https://sites.google.com/chromium.org/driver/)

---

## **Contributing**

We welcome contributions! Please follow these steps:

1. Fork the repository.
2. Create a new branch:
   ```bash
   git checkout -b feature-name
   ```
3. Make your changes and commit:
   ```bash
   git add .
   git commit -m "Add feature-name"
   ```
4. Push your changes:
   ```bash
   git push origin feature-name
   ```
5. Open a pull request.

---

## **Credits**

This project was developed by:

- **Muhammad Dafa Wisnu Galih**
  - Email: [dafa.w.dev@gmail.com](mailto:dafa.w.dev@gmail.com)
  - GitHub: [mdfwg](https://github.com/mdfwg)

- **NailFaaz**
  - Email: [nailfaaz2004@gmail.com](mailto:nailfaaz2004@gmail.com)
  - GitHub: [Nailfaaz](https://github.com/Nailfaaz)
