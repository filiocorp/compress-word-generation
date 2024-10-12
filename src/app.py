import sys

import requests
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS  # Import the CORS module
import os
import subprocess
from pdf2docx import Converter
import tempfile
import datetime
from PyPDF2 import PdfReader, PdfWriter
import base64
import io
import json
import cloudconvert
import zipfile
import logging


app = Flask(__name__)
CORS(app)  # This will enable CORS for all routes. You can also configure it to only enable for specific routes or origins.
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)



# Health check endpoint
@app.route("/health", methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route("/compressPdf", methods=['POST'])
def compressPdf():
    try:
        log_structured("DEBUG", "Request received")
        sys.stdout.flush())

        bucketName = 'Replace with your CLOUD bucket name' 
        bucket = storage_client.bucket(bucketName)
        logging.debug("Request received")
        data = request.get_json(force=True)
        template = data.get('template')
        pdfFilePaths = data.get('pdfFilePaths')
        template = data.get('template')
        reportName = data.get('reportName', 'report')
        isDocx = data.get('isDocx', False)
        numPages = data.get('numPages', 0)
        log_structured("DEBUG", "Request data received")
        sys.stdout.flush()
        # Download the PDFs from GCS and merge them
        pdf_buffers = {}
        for pdfFilePath in pdfFilePaths:
            # Extract the start page number from the filename
            # Assuming the filename format is 'REPORT_DOWNLOADS/reportId/reportName-startPage.pdf'
            filename = os.path.basename(pdfFilePath)
            startPageStr = filename.replace(reportName + '-', '').replace('.pdf', '')
            try:
                startPage = int(startPageStr)
            except ValueError:
                startPage = 0  # Default to 0 if parsing fails

            # Download the PDF from GCS
            blob = bucket.blob(pdfFilePath)
            pdf_data = blob.download_as_bytes()
            pdf_buffers[startPage] = pdf_data
        log_structured("DEBUG", "PDFs downloaded successfully")
        # Sort pdf_buffers based on start page numbers
        sorted_keys = sorted(pdf_buffers.keys())
        sorted_pdf_buffers = [pdf_buffers[key] for key in sorted_keys]
        log_structured("DEBUG", "PDFs sorted successfully")
        # Create temporary paths for input and output files
        tempInputPdfPath = os.path.join(tmpDir, f"inputPdf-{get_random_string(15)}-{int(datetime.datetime.now().timestamp())}.pdf")
        tempOutputPdfPath = os.path.join(tmpDir, f"outputPdf-{get_random_string(15)}-{int(datetime.datetime.now().timestamp())}.pdf")

        # Merge PDF buffers
        try:
            writer = PdfWriter()
            for pdf_data in sorted_pdf_buffers:
                reader = PdfReader(io.BytesIO(pdf_data))
                for page in reader.pages:
                    writer.add_page(page)
            with open(tempInputPdfPath, 'wb') as merged_pdf:
                writer.write(merged_pdf)
        except Exception as e:
            logging.exception("An error occurred in compressPdf:")
            return jsonify({"error": "Failed to merge PDFs", "details": str(e)}), 500
        log_structured("DEBUG", "PDFs merged successfully")
        # Determine the Ghostscript command
        gsCommand = determine_gs_command(tempInputPdfPath, tempOutputPdfPath)
        log_structured("DEBUG", "Ghostscript command determined successfully")
        try:
            # Execute the Ghostscript command
            subprocess.run(gsCommand, shell=True, check=True)
            log_structured("DEBUG", "PDF compression successful")
            # Generate a truly unique file name using a random string and the current timestamp
            randomString = get_random_string(15)
            pdfFileName = f"REPORT_DOWNLOADS/report-{int(datetime.datetime.now().timestamp())}-{randomString}/{reportName}.pdf"
            docxFilePath = tempOutputPdfPath.replace('.pdf', '.docx')
            # Generate a unique file name for the DOCX file
            log_structured("DEBUG", "Generating unique file names")
            docxFileName = f"REPORT_DOWNLOADS/report-{int(datetime.datetime.now().timestamp())}-{randomString}/{reportName}.docx"
            if isDocx:
                # Convert the compressed PDF to DOCX
                cv = Converter(tempOutputPdfPath)
                # Apply the custom settings
                cv.settings = {
                    'clip_image_res_ratio': 1.0,
                    'multi_processing': True,
                    'cpu_count': 6,
                    "start": 0,
                    "end": numPages,
                    # "line_overlap_threshold": 0.9,
                    # "max_line_spacing_ratio": 1,
                    # "line_break_width_ratio": 0.5,
                    # "debug": True,
                    # ... add any other settings you need here
                }
                cv.convert(docxFilePath)
                cv.close()

                # Upload DOCX to GCS
                docx_blob = bucket.blob(docxFileName)
                docx_blob.upload_from_filename(docxFilePath)
                safe_unlink(docxFilePath)

                # Generate signed URL for DOCX
                docx_url = docx_blob.generate_signed_url(
                    version="v4",
                    expiration=datetime.timedelta(hours=24),
                    method="GET"
                )
                return {"url": docx_url}, 200

            else:
                log_structured("DEBUG", "Uploading compressed PDF to GCS")
                output_blob = bucket.blob(pdfFileName)
                output_blob.upload_from_filename(tempOutputPdfPath)
                log_structured("DEBUG", "PDF uploaded successfully", tempOutputPdfPath=tempOutputPdfPath)


                pdf_url = "" # Generate a URL for the PDF
                log_structured("DEBUG", "Signed URL generated successfully: " + pdf_url)
                return {"url": pdf_url}, 200

        except subprocess.CalledProcessError as error:
            return {"error": "PDF compression failed", "details": str(error)}, 500

        finally:
            # Cleanup: Remove the temporary input and output files
            safe_unlink(tempInputPdfPath)
            safe_unlink(tempOutputPdfPath)
    except Exception as e:
        log_structured("ERROR", "An error occurred in compressPdf", error=str(e))
        return jsonify({"error": "Internal server error", "details": str(e)}), 500
def determine_gs_command(input_pdf, output_pdf):
    """
    Determine the Ghostscript 10.04.0 command based on environment.
    This version includes options to flatten the PDF, embed fonts, and optimize text rendering.
    """
    # Common options for all environments
    common_opts = [
        "-dNOPAUSE", "-dBATCH", "-dQUIET",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        "-dPDFSETTINGS=/printer",  # High-quality settings; adjust as needed
        # "-dEmbedAllFonts=true",  # Ensures all fonts are embedded
        # "-dSubsetFonts=true",  # Subset fonts to reduce size
        # "-dCompressFonts=true",  # Compress fonts in the PDF
        # "-dDetectDuplicateImages=true",  # Helps reduce size by detecting duplicate images
        f"-sOutputFile={output_pdf}",
        input_pdf
    ]

    return f"gs {' '.join(common_opts)}"


def get_random_string(length):
    import random
    import string
    characters = string.ascii_letters + string.digits
    random_string = ''.join(random.choice(characters) for i in range(length))
    return random_string

def safe_unlink(filePath):
    try:
        if os.path.exists(filePath):
            os.unlink(filePath)
    except Exception as cleanupError:
        print(f"Error cleaning up file {filePath}: {cleanupError}")



def ocr_pdf(input_path, output_path):
    try:
        # Run OCRmyPDF with input and output paths
        subprocess.run(['ocrmypdf', input_path, output_path], check=True)
        print("OCR complete and the output PDF is now searchable.")
    except subprocess.CalledProcessError as e:
        print("An error occurred during OCR processing:", e)


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8000))
    print(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port)
