# PDF Compression and Conversion Service

This service provides a REST API for compressing PDF files and optionally converting them to DOCX format using Ghostscript and pdf2docx.

## Features
- Compress PDF files using Ghostscript.
- Merge multiple PDF files and compress them.
- Convert compressed PDF files to DOCX format.
- Upload processed files to Google Cloud Storage.
- Generate signed URLs for downloading processed files.

## Endpoints

### Health Check
- **GET** `/health`
  - Returns a JSON object indicating the health status of the service.

### PDF Compression
- **POST** `/compressPdf`
  - Compresses PDF files and optionally converts them to DOCX format.
  - **Request Body**:
    ```json
    {
      "template": "<template_name>",
      "pdfFilePaths": ["<path_to_pdf1>", "<path_to_pdf2>"],
      "reportName": "<report_name>",
      "isDocx": true/false,
      "numPages": 0
    }
    ```
  - **Response**:
    ```json
    {
      "url": "<signed_url>"
    }
    ```

## Requirements
To run this service, you will need to install the following dependencies:

- Python 3.8 or higher
- Flask
- Ghostscript (AGPL-licensed)
- pdf2docx 0.5.8
- PyPDF2
- Google Cloud SDK (for Google Cloud Storage integration)

Install dependencies using the following command:

```bash
pip install -r requirements.txt
