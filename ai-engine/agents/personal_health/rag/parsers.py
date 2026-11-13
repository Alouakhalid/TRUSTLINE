"""Structure-aware document parsers for medical knowledge corpus (PDF, DOCX, TXT, JSON)."""
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import fitz  # PyMuPDF
import docx  # python-docx

from .schemas import DocumentType, TrustStatus, MedicalKnowledgeDocument

@dataclass
class ParsedSection:
    """A structurally identified section within a medical document."""
    title: str
    hierarchy: List[str] = field(default_factory=list)
    content: str = ""
    page_number: Optional[int] = None
    tables: List[List[List[str]]] = field(default_factory=list)
    citation_reference: Optional[str] = None

class MedicalDocumentParsingError(Exception):
    """Raised when a medical knowledge document cannot be parsed."""
    pass

class KnowledgeParserSecurityValidator:
    """Validates file size, extensions, and guards against ZIP/decompression bombs."""
    ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".json"}
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
    MAX_ZIP_ENTRIES = 1000
    MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024  # 100 MB

    @classmethod
    def validate_file_size(cls, file_bytes: bytes, filename: str = "document"):
        """Verify file bytes do not exceed size limit or 0-byte minimum."""
        if len(file_bytes) == 0:
            raise MedicalDocumentParsingError(f"Document '{filename}' is empty (0 bytes).")
        if len(file_bytes) > cls.MAX_FILE_SIZE:
            raise MedicalDocumentParsingError(f"File size exceeds safety limit of 50MB: {len(file_bytes)} bytes.")

    @classmethod
    def validate_path(cls, filename: str):
        """Guard against directory traversal patterns."""
        if ".." in filename or filename.startswith("/") or filename.startswith("\\"):
            raise MedicalDocumentParsingError(f"Path traversal attempt detected in filename: '{filename}'.")

    @classmethod
    def validate(cls, file_bytes: bytes, filename: str) -> DocumentType:
        cls.validate_file_size(file_bytes, filename)
        cls.validate_path(filename)
        
        clean_name = Path(filename).name
        ext = Path(clean_name).suffix.lower()
        if ext not in cls.ALLOWED_EXTENSIONS:
            raise MedicalDocumentParsingError(f"Unsupported document extension: '{ext}'.")
        
        if ext == ".docx":
            cls._check_zip_bomb(file_bytes)
            return DocumentType.DOCX
        elif ext == ".pdf":
            return DocumentType.PDF
        elif ext in (".txt", ".md"):
            return DocumentType.TXT if ext == ".txt" else DocumentType.MARKDOWN
        elif ext == ".json":
            return DocumentType.JSON
        return DocumentType.GUIDELINE

    @classmethod
    def _check_zip_bomb(cls, file_bytes: bytes):
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                entries = z.infolist()
                if len(entries) > cls.MAX_ZIP_ENTRIES:
                    raise MedicalDocumentParsingError(f"DOCX contains too many files ({len(entries)}), potential archive bomb.")
                total_uncompressed = sum(e.file_size for e in entries)
                if total_uncompressed > cls.MAX_UNCOMPRESSED_BYTES:
                    raise MedicalDocumentParsingError(f"DOCX uncompressed size exceeds 100MB limit: {total_uncompressed} bytes.")
        except zipfile.BadZipFile as e:
            raise MedicalDocumentParsingError(f"Corrupted or invalid DOCX archive: {str(e)}") from e

class PDFKnowledgeParser:
    """Extracts sections, headings, tables, and page numbers from medical PDF documents."""

    @classmethod
    def parse(cls, file_bytes: bytes, filename: str) -> List[ParsedSection]:
        sections: List[ParsedSection] = []
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception as exc:
            raise MedicalDocumentParsingError(f"Failed to open PDF document '{filename}': {str(exc)}") from exc

        if doc.page_count == 0:
            doc.close()
            raise MedicalDocumentParsingError(f"PDF document '{filename}' contains 0 pages.")

        current_section = ParsedSection(title="Document Header", page_number=1)
        
        for page_idx in range(doc.page_count):
            page_num = page_idx + 1
            page = doc.load_page(page_idx)
            text = page.get_text("text").strip()
            
            if not text:
                continue

            # Detect lines that look like headings
            lines = text.split("\n")
            buffer_lines: List[str] = []
            
            for line in lines:
                s_line = line.strip()
                if not s_line:
                    continue
                
                # Check for heading pattern: e.g. "SECTION 4.2", "4.2 Cardiovascular Protocols", or ALL CAPS short lines
                is_heading = bool(
                    re.match(r"^(?:SECTION|CHAPTER|STANDARD|PROTOCOL|\d+\.\d+)", s_line, re.IGNORECASE)
                    or (s_line.isupper() and len(s_line) < 60 and not s_line.endswith("."))
                )
                
                if is_heading:
                    if buffer_lines:
                        current_section.content += "\n".join(buffer_lines) + "\n"
                        buffer_lines = []
                    if current_section.content.strip():
                        sections.append(current_section)
                    current_section = ParsedSection(
                        title=s_line,
                        hierarchy=[s_line],
                        page_number=page_num
                    )
                else:
                    buffer_lines.append(s_line)
            
            if buffer_lines:
                current_section.content += "\n".join(buffer_lines) + "\n"
                buffer_lines = []
        
        if current_section.content.strip():
            sections.append(current_section)
        
        doc.close()
        if not sections or all(not s.content.strip() for s in sections):
            raise MedicalDocumentParsingError(f"No extractable text found in PDF document '{filename}'.")
        return sections

class DOCXKnowledgeParser:
    """Extracts sections, headings, paragraphs, and tables from DOCX medical documents."""

    @classmethod
    def parse(cls, file_bytes: bytes, filename: str) -> List[ParsedSection]:
        try:
            doc = docx.Document(io.BytesIO(file_bytes))
        except Exception as exc:
            raise MedicalDocumentParsingError(f"Failed to open DOCX document '{filename}': {str(exc)}") from exc

        sections: List[ParsedSection] = []
        current_section = ParsedSection(title="Overview", page_number=1)
        active_hierarchy: List[str] = []

        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue
            
            style_name = p.style.name if p.style else ""
            if "Heading" in style_name or re.match(r"^\d+\.\d+", text):
                if current_section.content.strip() or current_section.tables:
                    sections.append(current_section)
                active_hierarchy = [text]
                current_section = ParsedSection(
                    title=text,
                    hierarchy=list(active_hierarchy),
                    page_number=1
                )
            else:
                current_section.content += text + "\n"

        for table in doc.tables:
            table_rows: List[List[str]] = []
            for row in table.rows:
                row_vals = [cell.text.strip() for cell in row.cells]
                table_rows.append(row_vals)
            if table_rows:
                current_section.tables.append(table_rows)
                # Render table text as markdown inside content for robust lexical retrieval
                md_table = "\n" + " | ".join(table_rows[0]) + "\n"
                md_table += " | ".join(["---"] * len(table_rows[0])) + "\n"
                for r in table_rows[1:]:
                    md_table += " | ".join(r) + "\n"
                current_section.content += md_table + "\n"

        if current_section.content.strip() or current_section.tables:
            sections.append(current_section)

        if not sections or all(not s.content.strip() for s in sections):
            raise MedicalDocumentParsingError(f"No extractable text found in DOCX document '{filename}'.")
        return sections

class TextKnowledgeParser:
    """Extracts sections from Markdown and Plain Text medical documents."""

    @classmethod
    def parse(cls, file_bytes: bytes, filename: str) -> List[ParsedSection]:
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = file_bytes.decode("latin-1")
            except Exception as exc:
                raise MedicalDocumentParsingError(f"Encoding error parsing '{filename}': {str(exc)}") from exc

        if not text.strip():
            raise MedicalDocumentParsingError(f"Text document '{filename}' is empty.")

        sections: List[ParsedSection] = []
        lines = text.split("\n")
        current_section = ParsedSection(title="Introduction", page_number=1)
        buffer_lines: List[str] = []

        for line in lines:
            s_line = line.strip()
            if s_line.startswith("#"):
                if buffer_lines:
                    current_section.content += "\n".join(buffer_lines) + "\n"
                    sections.append(current_section)
                    buffer_lines = []
                h_title = re.sub(r"^#+\s*", "", s_line)
                current_section = ParsedSection(title=h_title, hierarchy=[h_title], page_number=1)
            else:
                buffer_lines.append(line)

        if buffer_lines:
            current_section.content += "\n".join(buffer_lines) + "\n"
        if current_section.content.strip():
            sections.append(current_section)

        return sections

class JSONKnowledgeParser:
    """Parses curated medical knowledge and protocol JSON dictionaries."""

    @classmethod
    def parse(cls, file_bytes: bytes, filename: str) -> List[ParsedSection]:
        try:
            data = json.loads(file_bytes.decode("utf-8"))
        except Exception as exc:
            raise MedicalDocumentParsingError(f"Invalid JSON in '{filename}': {str(exc)}") from exc

        items = data if isinstance(data, list) else [data]
        sections: List[ParsedSection] = []

        for item in items:
            title = item.get("title") or item.get("doc_id") or "Clinical Knowledge Entry"
            excerpt = item.get("excerpt") or item.get("content") or json.dumps(item)
            domain = item.get("medical_domain", "Aerospace Medicine")
            ref = item.get("citation_reference", "")
            content = f"Title: {title}\nDomain: {domain}\nCitation: {ref}\n\n{excerpt}"
            sections.append(ParsedSection(
                title=title,
                hierarchy=[domain, title],
                content=content,
                page_number=1,
                citation_reference=ref
            ))
        return sections
