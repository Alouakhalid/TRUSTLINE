"""Cross-agent evidence registry and quarantine audit service for the Supervisor."""
from typing import Dict, List, Any
from ..schemas.assessment import EvidenceRegistryItem

class EvidenceRegistryService:
    """Consolidates evidence across Sensor Quality, Personal Health, and Risk Assessment agents."""

    @classmethod
    def compile_and_audit_registry(cls, state: Dict[str, Any]) -> List[EvidenceRegistryItem]:
        """Aggregate evidence items across upstream agent outputs and enforce scientific quarantine guards."""
        registry: List[EvidenceRegistryItem] = []

        sqr = state.get("sensor_quality_result") or {}
        sensors = sqr.get("sensors", {})
        for s_name, s_res in sensors.items():
            status_val = s_res.get("status")
            score = s_res.get("quality_score", 0.0)
            is_quarantined = status_val == "INVALID" or s_res.get("critical_failure", False)
            q_reason = None
            if is_quarantined:
                q_reason = f"Sensor {s_name} marked INVALID by DSP quality inspection engine (score={score:.4f})"
            registry.append(EvidenceRegistryItem(
                evidence_id=f"EV-SQ-{s_name}",
                source_agent="sensor_quality_agent",
                domain="DATA_QUALITY_RELATED",
                metric_name=f"{s_name}_quality_score",
                observed_value=score,
                validity_status=status_val or "VALID",
                is_quarantined=is_quarantined,
                quarantine_reason=q_reason,
                provenance=f"Sensor Quality Agent DSP Pipeline ({s_name})"
            ))

        pha = state.get("personal_health_result") or {}
        core_feats = pha.get("core_features") or {}
        hrv_diag = pha.get("hrv_diagnostics") or {}

        ecg_info = sensors.get("ECG", {})
        ecg_quarantined = ecg_info.get("status") == "INVALID" or ecg_info.get("critical_failure", False)

        resp_info = sensors.get("RESP", {})
        resp_quarantined = resp_info.get("status") == "INVALID" or resp_info.get("critical_failure", False)

        temp_info = sensors.get("TEMP", {})
        temp_quarantined = temp_info.get("status") == "INVALID" or temp_info.get("critical_failure", False)

        eda_info = sensors.get("EDA", {})
        eda_quarantined = eda_info.get("status") == "INVALID" or eda_info.get("critical_failure", False)

        if "hr_mean_bpm" in core_feats and core_feats["hr_mean_bpm"] is not None:
            registry.append(EvidenceRegistryItem(
                evidence_id="EV-PHY-HR-MEAN",
                source_agent="personal_health_agent",
                domain="CARDIOVASCULAR",
                metric_name="heart_rate_mean",
                observed_value=core_feats["hr_mean_bpm"],
                validity_status="INVALID" if ecg_quarantined else "VALID",
                is_quarantined=ecg_quarantined,
                quarantine_reason="Source ECG signal marked INVALID by DSP inspection" if ecg_quarantined else None,
                provenance="Personal Health Agent ECG Core-14 Extraction"
            ))

        rmssd = core_feats.get("hrv_rmssd_ms", 0.0)
        hrv_status = hrv_diag.get("hrv_status", "ZERO_VARIABILITY") if hrv_diag else "ZERO_VARIABILITY"
        is_hrv_invalid = rmssd < 1.0 or hrv_status == "ZERO_VARIABILITY" or ecg_quarantined
        q_reason = "Zero variability artifact detected; quarantined from autonomic cardiovascular inference"
        if ecg_quarantined:
            q_reason = "Source ECG signal marked INVALID by DSP inspection"
        registry.append(EvidenceRegistryItem(
            evidence_id="EV-PHY-HRV-RMSSD",
            source_agent="personal_health_agent",
            domain="CARDIOVASCULAR",
            metric_name="hrv_rmssd",
            observed_value=rmssd,
            validity_status="INVALID" if is_hrv_invalid else "VALID",
            is_quarantined=is_hrv_invalid,
            quarantine_reason=q_reason if is_hrv_invalid else None,
            provenance="Personal Health Agent ECG R-Peak Timing"
        ))

        if "resp_rate_bpm" in core_feats and core_feats["resp_rate_bpm"] is not None:
            registry.append(EvidenceRegistryItem(
                evidence_id="EV-PHY-RESP-RATE",
                source_agent="personal_health_agent",
                domain="RESPIRATORY",
                metric_name="respiratory_rate",
                observed_value=core_feats["resp_rate_bpm"],
                validity_status="INVALID" if resp_quarantined else "VALID",
                is_quarantined=resp_quarantined,
                quarantine_reason="Source RESP signal marked INVALID by DSP inspection" if resp_quarantined else None,
                provenance="Personal Health Agent Respiration Peak Frequency Analysis"
            ))

        if "temp_mean" in core_feats and core_feats["temp_mean"] is not None:
            t_validity = "INVALID" if temp_quarantined else "DEGRADED"
            t_reason = "Source TEMP signal marked INVALID by DSP inspection" if temp_quarantined else "Peripheral skin temperature; degraded for core thermoregulatory inference"
            registry.append(EvidenceRegistryItem(
                evidence_id="EV-PHY-TEMP-MEAN",
                source_agent="personal_health_agent",
                domain="THERMOREGULATORY",
                metric_name="temperature_mean",
                observed_value=core_feats["temp_mean"],
                validity_status=t_validity,
                is_quarantined=temp_quarantined,
                quarantine_reason=t_reason,
                provenance="Personal Health Agent Thermal Telemetry"
            ))

        if "eda_mean" in core_feats and core_feats["eda_mean"] is not None:
            registry.append(EvidenceRegistryItem(
                evidence_id="EV-PHY-EDA-MEAN",
                source_agent="personal_health_agent",
                domain="PSYCHOLOGICAL_AND_COGNITIVE",
                metric_name="eda_mean",
                observed_value=core_feats["eda_mean"],
                validity_status="INVALID" if eda_quarantined else "VALID",
                is_quarantined=eda_quarantined,
                quarantine_reason="Source EDA signal marked INVALID by DSP inspection" if eda_quarantined else None,
                provenance="Personal Health Agent Electrodermal Tonic Mean"
            ))

        base_dev = state.get("personal_baseline_deviation") or pha.get("personal_baseline_deviation") or {}
        dev_report = base_dev.get("deviation_report") or {}
        feat_devs = dev_report.get("feature_deviations") or {}
        dev_scores = base_dev.get("deviation_scores") or {}

        if feat_devs:
            for f_name, f_data in feat_devs.items():
                z_score = f_data.get("robust_z_score", 0.0)
                is_valid = f_data.get("is_valid", True)
                rej_reason = f_data.get("rejection_reason")
                val_status = "VALID" if is_valid else "INVALID"
                b_ver = dev_report.get("baseline_version", 1)
                b_ctx = dev_report.get("applied_context", "UNKNOWN")
                b_mad = f_data.get("baseline_mad", 0.0)
                prov_str = f"Personal Health Baseline Engine (v{b_ver}, Context: {b_ctx}, MAD={b_mad:.2f})"
                registry.append(EvidenceRegistryItem(
                    evidence_id=f"EV-BASE-{f_name.upper()}",
                    source_agent="personal_health_agent",
                    domain="PHYSIOLOGICAL_BASELINE",
                    metric_name=f"baseline_deviation_{f_name.lower()}",
                    observed_value=z_score,
                    validity_status=val_status,
                    is_quarantined=not is_valid,
                    quarantine_reason=rej_reason if not is_valid else None,
                    provenance=prov_str
                ))
        elif dev_scores:
            for f_name, z_val in dev_scores.items():
                registry.append(EvidenceRegistryItem(
                    evidence_id=f"EV-BASE-{f_name.upper()}",
                    source_agent="personal_health_agent",
                    domain="PHYSIOLOGICAL_BASELINE",
                    metric_name=f"baseline_deviation_{f_name.lower()}",
                    observed_value=z_val,
                    validity_status="VALID",
                    is_quarantined=False,
                    quarantine_reason=None,
                    provenance=f"Personal Health Baseline Engine (Deviation Score for {f_name})"
                ))
        else:
            b_stat = pha.get("baseline_status") or base_dev.get("baseline_status") or "NOT_AVAILABLE"
            b_str = getattr(b_stat, "value", str(b_stat)).lower()
            is_unavail = "not_available" in b_str or "insufficient" in b_str or "invalid" in b_str
            registry.append(EvidenceRegistryItem(
                evidence_id="EV-BASE-STATUS",
                source_agent="personal_health_agent",
                domain="PHYSIOLOGICAL_BASELINE",
                metric_name="baseline_readiness_status",
                observed_value=getattr(b_stat, "value", str(b_stat)),
                validity_status="NOT_AVAILABLE" if is_unavail else "VALID",
                is_quarantined=False,
                quarantine_reason="Personal baseline unestablished; population reference or deferred comparison active" if is_unavail else None,
                provenance="Personal Health Baseline Readiness Registry"
            ))

        symptoms = pha.get("symptom_findings", [])
        if not symptoms:
            registry.append(EvidenceRegistryItem(
                evidence_id="EV-SYM-UNSUBMITTED",
                source_agent="personal_health_agent",
                domain="GENERAL_PHYSIOLOGICAL",
                metric_name="symptom_status_unsubmitted",
                observed_value="no_symptoms_submitted",
                validity_status="NOT_AVAILABLE",
                is_quarantined=False,
                quarantine_reason="Unsubmitted symptoms represent unknown symptom status, not clinical absence of symptoms",
                provenance="Personal Health Intake (No Questionnaire Submitted)"
            ))
        else:
            for idx, sym in enumerate(symptoms):
                s_type = sym.get("symptom_type", f"reported_{idx+1}")
                s_cat = sym.get("symptom_category", "GENERAL_PHYSIOLOGICAL")
                s_sev = sym.get("severity", "nominal")
                registry.append(EvidenceRegistryItem(
                    evidence_id=f"EV-SYM-{idx+1}-{s_type.upper()}",
                    source_agent="personal_health_agent",
                    domain=s_cat if s_cat in ("CARDIOVASCULAR", "RESPIRATORY", "NEUROLOGICAL", "GENERAL_PHYSIOLOGICAL") else "GENERAL_PHYSIOLOGICAL",
                    metric_name=f"reported_symptom_{s_type}",
                    observed_value=sym.get("description") or s_type,
                    validity_status="VALID",
                    is_quarantined=False,
                    quarantine_reason=None,
                    provenance=f"Personal Health Agent Symptom Intake (Severity: {s_sev})"
                ))

        confirmed_records = state.get("confirmed_medical_records") or []
        for idx, raw_rec in enumerate(confirmed_records, start=1):
            rec = raw_rec if isinstance(raw_rec, dict) else raw_rec.model_dump()
            rec_id = rec.get("record_id") or str(idx)
            test_name = rec.get("test_name") or "clinical_test"
            num_val = rec.get("numeric_value")
            val_str = rec.get("value_string") or str(num_val)
            coll_date = rec.get("collection_date") or "N/A"
            conf_by = rec.get("confirmed_by") or "system"
            doc_id = rec.get("document_id") or "DOC"
            conflict_detected = bool(rec.get("conflict_detected", False))
            rec_astro = rec.get("astronaut_id") or state.get("astronaut_id") or "UNKNOWN"
            state_astro = state.get("astronaut_id") or "UNKNOWN"

            is_quarantined = False
            q_reason = None
            val_status = "VALID"

            if rec_astro == "UNKNOWN" or state_astro == "UNKNOWN" or rec_astro != state_astro:
                is_quarantined = True
                val_status = "INVALID"
                q_reason = "Quarantined: unverified or mismatching astronaut identity"
            elif conflict_detected:
                is_quarantined = True
                val_status = "CONFLICTING"
                q_reason = f"Quarantined: conflicting laboratory extractions detected ({test_name})"

            registry.append(EvidenceRegistryItem(
                evidence_id=f"EV-MED-CONFIRMED-{rec_id}",
                source_agent="medical_records_repository",
                domain="GENERAL_PHYSIOLOGICAL",
                metric_name=test_name.lower().replace(" ", "_"),
                observed_value=num_val if num_val is not None else val_str,
                validity_status=val_status,
                is_quarantined=is_quarantined,
                quarantine_reason=q_reason,
                provenance=f"Historical Clinical Record ({doc_id}, Coll: {coll_date}, Confirmed by: {conf_by})"
            ))

        pending_records = state.get("pending_medical_records") or []
        for idx, raw_p in enumerate(pending_records, start=1):
            p_rec = raw_p if isinstance(raw_p, dict) else raw_p.model_dump()
            p_id = p_rec.get("record_id") or str(idx)
            p_name = p_rec.get("test_name") or "pending_test"
            p_val = p_rec.get("extracted_value") or p_rec.get("normalized_value")
            p_doc = p_rec.get("document_id") or "DOC"
            registry.append(EvidenceRegistryItem(
                evidence_id=f"EV-DOC-PENDING-{p_id}",
                source_agent="document_ingestion_service",
                domain="GENERAL_PHYSIOLOGICAL",
                metric_name=p_name.lower().replace(" ", "_"),
                observed_value=p_val,
                validity_status="PENDING_REVIEW",
                is_quarantined=True,
                quarantine_reason="Pending clinical human-in-the-loop review",
                provenance=f"Medical Document Ingestion Quarantine ({p_doc})"
            ))

        rag_res = state.get("medical_rag_result") or {}
        passages = rag_res.get("retrieved_passages") or []
        retrieval_status = str(rag_res.get("retrieval_status") or "SUCCESS")
        for p in passages:
            p_dict = p if isinstance(p, dict) else p.model_dump()
            chunk_id = p_dict.get("chunk_id", "UNKNOWN")
            doc_id = p_dict.get("document_id", "DOC")
            title = p_dict.get("title") or "Medical Knowledge"
            section = p_dict.get("section_title") or "General"
            rel_score = float(p_dict.get("relevance_score", 0.0))
            excerpt = p_dict.get("excerpt") or p_dict.get("passage_text") or ""
            cit_ref = p_dict.get("citation_reference") or f"{doc_id}:{section}"
            source_org = p_dict.get("source_organization") or "NASA / Medical Operations"
            is_conflicting = (
                "CONFLICT" in retrieval_status
                or bool(p_dict.get("conflict_detected", False))
                or p_dict.get("validity_status") == "CONFLICTING"
            )

            registry.append(EvidenceRegistryItem(
                evidence_id=f"EV-KNOW-{chunk_id}",
                source_agent="medical_knowledge_rag_service",
                domain="CLINICAL_KNOWLEDGE",
                metric_name=f"knowledge_passage_{chunk_id.lower().replace('-', '_')}",
                observed_value=excerpt,
                validity_status="CONFLICTING" if is_conflicting else "VALID",
                is_quarantined=is_conflicting,
                quarantine_reason=f"Conflicting knowledge sources detected for: {cit_ref}" if is_conflicting else None,
                provenance=f"Medical RAG Hybrid Retrieval ({title}, Ref: {cit_ref}, Source: {source_org}, Score: {rel_score:.3f})"
            ))

        injected = state.get("injected_evidence") or []
        for raw in injected:
            if isinstance(raw, dict):
                eid = raw.get("evidence_id", "EV-INJECTED-UNKNOWN")
                s_agent = raw.get("source_agent")
                prov = raw.get("provenance")
                val_status = raw.get("validity_status", "VALID")
                is_q = raw.get("is_quarantined", False)
                q_reason = raw.get("quarantine_reason")
                if not s_agent or s_agent in ("UNKNOWN", "", "None") or not prov or not str(prov).strip():
                    is_q = True
                    val_status = "INVALID"
                    q_reason = f"Provenance audit failure: missing or malformed provenance (source_agent='{s_agent}', provenance='{prov}')"
                registry.append(EvidenceRegistryItem(
                    evidence_id=eid,
                    source_agent=s_agent or "UNKNOWN",
                    domain=raw.get("domain", "GENERAL_PHYSIOLOGICAL"),
                    metric_name=raw.get("metric_name", "injected_metric"),
                    observed_value=raw.get("observed_value"),
                    validity_status=val_status,
                    is_quarantined=is_q,
                    quarantine_reason=q_reason,
                    provenance=prov or ""
                ))
            elif isinstance(raw, EvidenceRegistryItem):
                registry.append(raw)

        existing_reg = state.get("evidence_registry") or []
        for raw in existing_reg:
            if isinstance(raw, dict):
                eid = raw.get("evidence_id", "EV-UNKNOWN")
                if not any(r.evidence_id == eid for r in registry):
                    s_agent = raw.get("source_agent")
                    prov = raw.get("provenance")
                    val_status = raw.get("validity_status", "VALID")
                    is_q = raw.get("is_quarantined", False)
                    q_reason = raw.get("quarantine_reason")
                    registry.append(EvidenceRegistryItem(
                        evidence_id=eid,
                        source_agent=s_agent or "UNKNOWN",
                        domain=raw.get("domain", "GENERAL_PHYSIOLOGICAL"),
                        metric_name=raw.get("metric_name", "unknown_metric"),
                        observed_value=raw.get("observed_value"),
                        validity_status=val_status,
                        is_quarantined=is_q,
                        quarantine_reason=q_reason,
                        provenance=prov or ""
                    ))
            elif isinstance(raw, EvidenceRegistryItem):
                if not any(r.evidence_id == raw.evidence_id for r in registry):
                    registry.append(raw)

        for item in registry:
            s_agent = getattr(item, "source_agent", None)
            prov = getattr(item, "provenance", None)
            is_malformed = (
                not s_agent
                or s_agent in ("UNKNOWN", "", "None")
                or not prov
                or not str(prov).strip()
            )
            if is_malformed:
                item.is_quarantined = True
                item.validity_status = "INVALID"
                item.quarantine_reason = f"Provenance audit failure: missing or malformed provenance (source_agent='{s_agent}', provenance='{prov}')"

        return registry
