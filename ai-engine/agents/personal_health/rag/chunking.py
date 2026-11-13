"""Structure-aware semantic chunker preserving medical section headers, tables, and page boundaries."""
import re
from typing import Dict, List, Optional, Any
from .parsers import ParsedSection
from .schemas import MedicalChunk, TrustStatus

class StructureAwareChunker:
    """Splits parsed sections into clinically coherent chunks with header context preservation."""

    def __init__(
        self,
        target_chunk_chars: int = 1500,
        chunk_overlap_chars: int = 250,
        min_chunk_chars: int = 100,
        min_chunk_tokens: Optional[int] = None,
        max_chunk_tokens: Optional[int] = None,
        overlap_tokens: Optional[int] = None
    ):
        if max_chunk_tokens is not None:
            target_chunk_chars = max_chunk_tokens * 4
        if overlap_tokens is not None:
            chunk_overlap_chars = overlap_tokens * 4
        if min_chunk_tokens is not None:
            min_chunk_chars = min_chunk_tokens * 4
        self.target_chunk_chars = target_chunk_chars
        self.chunk_overlap_chars = min(chunk_overlap_chars, target_chunk_chars // 2)
        self.min_chunk_chars = min_chunk_chars

    def chunk_sections(
        self,
        sections: List[ParsedSection],
        document_id: str,
        document_title: str,
        citation_base: str,
        trust_status: TrustStatus = TrustStatus.OFFICIAL_GUIDELINE,
        medical_domain: str = "Aerospace Medicine"
    ) -> List[MedicalChunk]:
        """Convert parsed document sections into an ordered list of MedicalChunk objects."""
        chunks: List[MedicalChunk] = []
        chunk_idx = 1

        for s_idx, section in enumerate(sections, start=1):
            text = section.content.strip()
            if not text:
                continue

            sec_title = section.title or f"Section {s_idx}"
            hierarchy_str = " > ".join(section.hierarchy) if section.hierarchy else sec_title
            header_prefix = f"[{document_title} | {hierarchy_str}]\n"
            page_num = section.page_number

            # If section text comfortably fits within target size, keep it as single atomic chunk
            if len(text) <= self.target_chunk_chars:
                chunk_id = f"{document_id}_c{chunk_idx:03d}"
                chunks.append(MedicalChunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    document_title=document_title,
                    section_title=sec_title,
                    heading_hierarchy=section.hierarchy or [sec_title],
                    page_number=page_num,
                    chunk_index=chunk_idx,
                    content=header_prefix + text,
                    token_count=max(1, len(text) // 4),
                    table_data=section.tables if section.tables else None,
                    citation_reference=section.citation_reference or f"{citation_base}-Sec{s_idx}-P{page_num or 1}",
                    trust_status=trust_status,
                    medical_domain=medical_domain
                ))
                chunk_idx += 1
                continue

            # Section exceeds target size: split on paragraph boundaries
            paragraphs = re.split(r"\n\s*\n", text)
            current_buffer: List[str] = []
            current_len = 0

            for p in paragraphs:
                p_clean = p.strip()
                if not p_clean:
                    continue

                if current_len + len(p_clean) > self.target_chunk_chars and current_buffer:
                    # Flush current buffer as a chunk
                    chunk_text = "\n\n".join(current_buffer)
                    chunk_id = f"{document_id}_c{chunk_idx:03d}"
                    chunks.append(MedicalChunk(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        document_title=document_title,
                        section_title=sec_title,
                        heading_hierarchy=section.hierarchy or [sec_title],
                        page_number=page_num,
                        chunk_index=chunk_idx,
                        content=header_prefix + chunk_text,
                        token_count=max(1, len(chunk_text) // 4),
                        table_data=section.tables if section.tables else None,
                        citation_reference=section.citation_reference or f"{citation_base}-Sec{s_idx}-P{page_num or 1}",
                        trust_status=trust_status,
                        medical_domain=medical_domain
                    ))
                    chunk_idx += 1

                    # Retain overlap from end of buffer
                    overlap_buffer: List[str] = []
                    overlap_len = 0
                    for prev_p in reversed(current_buffer):
                        if overlap_len + len(prev_p) <= self.chunk_overlap_chars:
                            overlap_buffer.insert(0, prev_p)
                            overlap_len += len(prev_p)
                        else:
                            break
                    current_buffer = list(overlap_buffer)
                    current_len = overlap_len

                current_buffer.append(p_clean)
                current_len += len(p_clean)

            if current_buffer:
                chunk_text = "\n\n".join(current_buffer)
                if len(chunk_text) >= self.min_chunk_chars or not chunks:
                    chunk_id = f"{document_id}_c{chunk_idx:03d}"
                    chunks.append(MedicalChunk(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        section_title=sec_title,
                        heading_hierarchy=section.hierarchy or [sec_title],
                        page_number=page_num,
                        chunk_index=chunk_idx,
                        content=header_prefix + chunk_text,
                        token_count=max(1, len(chunk_text) // 4),
                        table_data=section.tables if section.tables else None,
                        citation_reference=section.citation_reference or f"{citation_base}-Sec{s_idx}-P{page_num or 1}",
                        trust_status=trust_status,
                        medical_domain=medical_domain
                    ))
                    chunk_idx += 1

        return chunks
