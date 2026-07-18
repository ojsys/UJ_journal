"""
Utility functions for the journal application.
"""
import os
from docx import Document
from django.core.files.base import ContentFile
import io


def sanitize_document_metadata(document_path):
    """
    Remove author information from Word document metadata.
    Returns a sanitized BytesIO object that can be saved as a file.

    Args:
        document_path: Path to the document file

    Returns:
        BytesIO object containing the sanitized document
    """
    try:
        # Load the document
        doc = Document(document_path)

        # Access and clear core properties (metadata)
        core_props = doc.core_properties
        core_props.author = ""
        core_props.last_modified_by = ""
        core_props.revision = 1
        core_props.created = None
        core_props.modified = None
        core_props.comments = ""
        core_props.keywords = ""
        core_props.subject = ""
        core_props.title = ""

        # Save to BytesIO object
        sanitized_io = io.BytesIO()
        doc.save(sanitized_io)
        sanitized_io.seek(0)

        return sanitized_io
    except Exception as e:
        # If sanitization fails, return None
        # The view can decide whether to serve the original or show an error
        print(f"Error sanitizing document: {e}")
        return None


def get_sanitized_filename(original_filename, anonymized_id):
    """
    Generate a sanitized filename using the anonymized identifier.

    Args:
        original_filename: Original filename
        anonymized_id: Anonymized identifier for the submission

    Returns:
        Sanitized filename
    """
    # Get file extension
    _, ext = os.path.splitext(original_filename)
    # Return sanitized name
    return f"{anonymized_id}{ext}"
