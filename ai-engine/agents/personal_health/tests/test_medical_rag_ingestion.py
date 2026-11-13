"""Tests for Medical Knowledge RAG Ingestion Pipeline: parsers, chunking, deduplication, and security."""
import io
import json
import pytest
import fitz
from docx import Document

from personal_health.rag.parsers import (
    PDFKnowledgeParser,
    DOCXKnowledgeParser,
    TextKnowledgeParser,
    JSONKnowledgeParser,
    KnowledgeParserSecurityValidator,
    MedicalDocumentParsingError
)
from personal_health.rag.chunking import StructureAwareChunker
from personal_health.rag.schemas import DocumentType, TrustStatus
from personal_health.rag.service import MedicalKnowledgeRAGService

def create_synthetic_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 72), "SECTION 1.0 EMERGENCY PROTOCOL\nResting heart rate > 160 bpm is critical red-line.", fontsize=12)
    page2 = doc.new_page(width=595, height=842)
    page2.insert_text((50, 72), "SECTION 2.0 INTERVENTIONS\nImmediate 100% O2 delivery and Flight Surgeon consult.", fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes

def create_synthetic_docx() -> bytes:
    doc = Document()
    doc.add_heading("Cardiovascular Adaptation In Microgravity", level=1)
    doc.add_paragraph("Cephalad fluid shift causes venous engorgement and initial facial edema.")
    doc.add_heading("Countermeasure Regimen", level=2)
    doc.add_paragraph("Daily cycle ergometer exercise at 75% VO2 max for 45 minutes.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()

def test_01_parse_pdf_knowledge():
    pdf_bytes = create_synthetic_pdf()
    KnowledgeParserSecurityValidator.validate_file_size(pdf_bytes, "test.pdf")
    sections = PDFKnowledgeParser.parse(pdf_bytes, "test.pdf")
    assert len(sections) >= 2
    assert any("EMERGENCY PROTOCOL" in s.title for s in sections)
    assert any("INTERVENTIONS" in s.title for s in sections)
    assert any("160 bpm" in s.content for s in sections)

def test_02_parse_docx_knowledge():
    docx_bytes = create_synthetic_docx()
    KnowledgeParserSecurityValidator.validate_file_size(docx_bytes, "test.docx")
    sections = DOCXKnowledgeParser.parse(docx_bytes, "test.docx")
    assert len(sections) >= 2
    assert any("Cardiovascular Adaptation" in s.title for s in sections)
    assert any("Countermeasure Regimen" in s.title for s in sections)
    assert any("Cephalad fluid shift" in s.content for s in sections)

def test_03_parse_txt_and_markdown():
    md_content = """# Section 1: Acoustic Monitoring
Continuous background sound pressure levels exceeding 65 dBA degrade astronaut sleep architecture.

## Countermeasures
Deploy active noise cancelling headsets during sleep periods.
"""
    md_bytes = md_content.encode("utf-8")
    sections = TextKnowledgeParser.parse(md_bytes, "acoustic.md")
    assert len(sections) >= 2
    assert any("Acoustic Monitoring" in s.title for s in sections)
    assert any("65 dBA" in s.content for s in sections)

def test_04_parse_json_knowledge():
    json_data = [
        {
            "doc_id": "TEST-001",
            "title": "Hypercapnia Thresholds in Exploration Vehicles",
            "medical_domain": "Environmental Health",
            "citation_reference": "NASA-STD-3001-CO2",
            "excerpt": "Ambient CO2 concentrations exceeding 3.0 mmHg correlate with astronaut headache reports."
        }
    ]
    raw_bytes = json.dumps(json_data).encode("utf-8")
    sections = JSONKnowledgeParser.parse(raw_bytes, "co2.json")
    assert len(sections) == 1
    assert sections[0].title == "Hypercapnia Thresholds in Exploration Vehicles"
    assert sections[0].citation_reference == "NASA-STD-3001-CO2"
    assert "3.0 mmHg" in sections[0].content

def test_05_content_hash_deduplication():
    rag = MedicalKnowledgeRAGService()
    pdf_bytes = create_synthetic_pdf()
    
    doc1 = rag.ingest_file(
        file_bytes=pdf_bytes,
        filename="dedup_test.pdf",
        doc_type=DocumentType.PDF,
        title="Dedup Test Protocol",
        trust_status=TrustStatus.MISSION_PROTOCOL
    )
    initial_doc_id = doc1.document_id
    initial_chunks = doc1.total_chunks
    
    # Ingest identical file again
    doc2 = rag.ingest_file(
        file_bytes=pdf_bytes,
        filename="dedup_test.pdf",
        doc_type=DocumentType.PDF,
        title="Dedup Test Protocol Duplicate",
        trust_status=TrustStatus.MISSION_PROTOCOL
    )
    assert doc2.document_id == initial_doc_id
    assert doc2.total_chunks == initial_chunks

def test_06_corrupt_and_empty_file_handling():
    with pytest.raises(MedicalDocumentParsingError):
        TextKnowledgeParser.parse(b"", "empty.txt")
        
    with pytest.raises(MedicalDocumentParsingError):
        PDFKnowledgeParser.parse(b"NOT_A_VALID_PDF", "corrupted.pdf")
        
    with pytest.raises(MedicalDocumentParsingError):
        JSONKnowledgeParser.parse(b"{invalid_json: true", "corrupted.json")

def test_07_decompression_bomb_and_path_traversal_guards():
    huge_bytes = b"A" * (51 * 1024 * 1024)
    with pytest.raises(MedicalDocumentParsingError) as exc_info:
        KnowledgeParserSecurityValidator.validate_file_size(huge_bytes, "huge.bin")
    assert "exceeds safety limit" in str(exc_info.value)

    with pytest.raises(MedicalDocumentParsingError) as exc_info:
        KnowledgeParserSecurityValidator.validate_path("../../etc/passwd")
    assert "Path traversal attempt detected" in str(exc_info.value)

def test_08_chunking_structure_awareness():
    chunker = StructureAwareChunker(min_chunk_tokens=30, max_chunk_tokens=150, overlap_tokens=20)
    pdf_bytes = create_synthetic_pdf()
    sections = PDFKnowledgeParser.parse(pdf_bytes, "test.pdf")
    
    chunks = chunker.chunk_sections(
        sections=sections,
        document_id="KNOW-TEST-123",
        document_title="Test Emergency Protocol",
        citation_base="NASA-TEST-2025",
        trust_status=TrustStatus.MISSION_PROTOCOL,
        medical_domain="Emergency Medicine"
    )
    
    assert len(chunks) >= 2
    for c in chunks:
        assert c.document_id == "KNOW-TEST-123"
        assert c.document_title == "Test Emergency Protocol"
        assert c.citation_reference.startswith("NASA-TEST-2025")
        assert c.trust_status == TrustStatus.MISSION_PROTOCOL
        assert len(c.content.strip()) > 0
