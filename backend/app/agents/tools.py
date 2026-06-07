"""
Tool Functions for Medical Diagnostic Workflow

These tools can be called by agents to perform specific tasks.
Each tool is a pure function that takes state and returns updated state or result.
"""
import json
import uuid
import re
import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from .state import AgentState
from .config import call_groq_llm
from .schemas import RAGTreatmentPlanOutput
from ..core.error_handling import (
    DatabaseError, DatabaseConnectionError, DatabaseIntegrityError,
    PDFGenerationError, MLModelError, MLModelLoadError, MLModelPredictionError,
    handle_database_error, safe_execute, format_error_for_user, log_error_with_context
)

logger = logging.getLogger(__name__)


def recommend_tests(symptoms: str, age: Optional[int] = None, gender: Optional[str] = None) -> list[str]:
    s = (symptoms or "").lower()
    tests: list[str] = []

    breath_issue = any(w in s for w in (
        "wheez", "asthma", "copd", "shortness", "breathless", "breathing difficulty",
        "tight chest", "obstruct", "fev", "spirom",
    ))
    infection = any(w in s for w in ("fever", "infection", "chills", "bacteria", "virus", "septic"))
    chest_issue = "chest" in s and any(w in s for w in ("pain", "pressure", "tight", "discomfort"))
    lung_issue = any(w in s for w in ("lung", "pneumonia", "infiltrate", "consolidation"))
    cough_only = "cough" in s and not infection and not chest_issue and not lung_issue
    allergy_cough = "allerg" in s and "cough" in s and not infection

    if infection or "fatigue" in s or "weakness" in s:
        tests.append("cbc")
    if chest_issue or lung_issue or infection or "pneumonia" in s:
        tests.append("xray")
    if breath_issue:
        tests.append("spirometry")
    elif allergy_cough or cough_only:
        tests.append("spirometry")

    seen: set[str] = set()
    ordered: list[str] = []
    for t in ("xray", "cbc", "spirometry"):
        if t in tests and t not in seen:
            ordered.append(t)
            seen.add(t)

    return ordered if ordered else ["spirometry"]


def format_test_results_for_llm(state: AgentState) -> str:
    """
    Format test results for LLM consumption.
    """
    test_results = []
    
    # X-ray results
    xray_result = state.get("xray_result")
    if xray_result and isinstance(xray_result, dict):
        if xray_result.get("status") != "skipped":
            prediction = xray_result.get("prediction", {})
            disease_name = prediction.get("disease_name", "Unknown")
            confidence = prediction.get("confidence", 0.0)
            test_results.append(f"X-ray Analysis: {disease_name} (confidence: {confidence:.1%})")
        else:
            test_results.append("X-ray: Not performed (skipped)")
    
    # Spirometry results
    spirometry_result = state.get("spirometry_result")
    if spirometry_result and isinstance(spirometry_result, dict):
        if spirometry_result.get("status") != "skipped":
            prediction = spirometry_result.get("prediction", {})
            pattern = prediction.get("pattern", "Unknown")
            severity = prediction.get("severity", "Unknown")
            input_values = spirometry_result.get("input_values", {})
            fev1 = input_values.get("fev1", "N/A")
            fvc = input_values.get("fvc", "N/A")
            test_results.append(
                f"Spirometry: Pattern={pattern}, Severity={severity}, "
                f"FEV1={fev1}L, FVC={fvc}L"
            )
        else:
            test_results.append("Spirometry: Not performed (skipped)")
    
    # CBC results
    cbc_result = state.get("cbc_result")
    if cbc_result and isinstance(cbc_result, dict):
        if cbc_result.get("status") != "skipped":
            prediction = cbc_result.get("prediction", {})
            disease_name = prediction.get("disease_name", "Unknown")
            confidence = prediction.get("confidence", 0.0)
            input_values = cbc_result.get("input_values", {})
            wbc = input_values.get("WBC", "N/A")
            rbc = input_values.get("RBC", "N/A")
            hgb = input_values.get("HGB", "N/A")
            test_results.append(
                f"CBC: {disease_name} (confidence: {confidence:.1%}), "
                f"WBC={wbc}, RBC={rbc}, HGB={hgb}"
            )
        else:
            test_results.append("CBC: Not performed (skipped)")
    
    if not test_results:
        return "No diagnostic test results available yet."
    
    return "\n\n".join(test_results)


def calculate_dosage_tool(state: AgentState) -> Dict[str, Any]:
    """
    Tool: Calculate medication dosages based on treatment plan and patient weight.
    Includes comprehensive error handling with fallback values.
    """
    from ..core.error_handling import LLMError, LLMInvalidResponseError
    
    treatment_plan = state.get("treatment_plan", [])
    patient_weight = state.get("patient_weight")
    patient_age = state.get("patient_age")
    
    if not treatment_plan:
        logger.warning("No treatment plan available for dosage calculation")
        return {"status": "error", "dosages": {}, "message": "No treatment plan available"}
    
    messages = [
        {
            "role": "system",
            "content": """You are a medical dosage calculator. Calculate appropriate dosages for medications based on:
            - Patient weight (in kg)
            - Patient age
            - Standard medical dosing guidelines
            - Medication name

            Return JSON: {"medication_name": {"dose": "...", "frequency": "...", "duration": "...", "notes": "..."}}"""
        },
        {
            "role": "user",
            "content": f"Weight: {patient_weight}kg, Age: {patient_age}yrs, Plan: {treatment_plan}"
        }
    ]
    
    try:
        response = call_groq_llm(messages, json_mode=True)
        
        # Parse JSON response
        response = response.strip()
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
        
        dosages = json.loads(response)
        
        if not isinstance(dosages, dict):
            raise LLMInvalidResponseError("Dosage calculation returned invalid format")
        
        logger.info("Successfully calculated medication dosages")
        return {"status": "success", "dosages": dosages}
        
    except LLMError as e:
        log_error_with_context(e, {"operation": "calculate_dosage"})
        # Return fallback dosages
        fallback_dosages = {}
        for treatment in treatment_plan:
            med_name = treatment.split(":")[0].strip() if ":" in treatment else treatment.split()[0]
            fallback_dosages[med_name] = {
                "dose": "As prescribed by doctor",
                "frequency": "As directed",
                "duration": "As per treatment plan",
                "notes": "Please consult with your healthcare provider for specific dosage instructions"
            }
        logger.warning("Using fallback dosages due to LLM error")
        return {"status": "partial", "dosages": fallback_dosages, "message": "Using standard dosages. Please consult your doctor."}
        
    except (json.JSONDecodeError, LLMInvalidResponseError) as e:
        log_error_with_context(e, {"operation": "calculate_dosage", "response_preview": response[:100] if 'response' in locals() else "N/A"})
        # Return fallback dosages
        fallback_dosages = {}
        for treatment in treatment_plan:
            med_name = treatment.split(":")[0].strip() if ":" in treatment else treatment.split()[0]
            fallback_dosages[med_name] = {
                "dose": "As prescribed by doctor",
                "frequency": "As directed",
                "duration": "As per treatment plan",
                "notes": "Please consult with your healthcare provider for specific dosage instructions"
            }
        return {"status": "partial", "dosages": fallback_dosages, "message": "Using standard dosages. Please consult your doctor."}
        
    except Exception as e:
        log_error_with_context(e, {"operation": "calculate_dosage"})
        return {"status": "error", "dosages": {}, "message": format_error_for_user(e, "calculating dosages")}


def generate_final_report_tool(state: AgentState) -> Dict[str, Any]:
    """
    Tool: Generate comprehensive final medical report.
    Includes error handling with fallback report generation.
    """
    from ..core.error_handling import LLMError
    
    test_results_text = format_test_results_for_llm(state)
    calculated_dosages = state.get("calculated_dosages", {})
    
    dosage_info_text = ""
    if calculated_dosages:
        dosage_info_text = "\n\n**Calculated Medication Dosages:**\n"
        for med, dose_info in calculated_dosages.items():
            dosage_info_text += f"- {med.capitalize()}: {dose_info.get('dose', 'N/A')} {dose_info.get('frequency', 'N/A')}\n"
            if dose_info.get('notes'):
                dosage_info_text += f"  Note: {dose_info.get('notes')}\n"
    
    messages = [
        {
            "role": "system",
            "content": """You are a medical report generator. Create a professional medical report for the patient.
            Include patient info, symptoms, test results, diagnosis, treatment, and dosages."""
        },
        {
            "role": "user",
            "content": f"""
            Patient: {state.get("patient_name")} ({state.get("patient_age")}yo)
            Symptoms: {state.get("symptoms")}
            Test Results: {test_results_text}
            Diagnosis: {state.get("diagnosis")}
            Treatment: {state.get("treatment_plan")}
            {dosage_info_text}
            """
        }
    ]
    
    try:
        report = call_groq_llm(messages, temperature=0.5)
        
        if not report or not report.strip():
            raise LLMInvalidResponseError("Empty report generated")
        
        logger.info("Successfully generated final medical report")
        return {"status": "success", "report": report}
        
    except LLMError as e:
        log_error_with_context(e, {"operation": "generate_final_report"})
        # Generate fallback report
        fallback_report = f"""
MEDICAL REPORT

Patient: {state.get('patient_name', 'N/A')}
Age: {state.get('patient_age', 'N/A')} years
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

SYMPTOMS:
{state.get('symptoms', 'Not provided')}

TEST RESULTS:
{test_results_text}

DIAGNOSIS:
{state.get('diagnosis', 'Pending')}

TREATMENT PLAN:
{chr(10).join([f"- {t}" for t in state.get('treatment_plan', [])])}

{dosage_info_text if dosage_info_text else ''}

FOLLOW-UP:
{state.get('followup_instruction', 'Please follow up as directed by your healthcare provider.')}

Note: This report was generated automatically. Please consult with your healthcare provider for any questions.
        """
        logger.warning("Using fallback report due to LLM error")
        return {"status": "partial", "report": fallback_report.strip(), "message": "Report generated with limited formatting."}
        
    except Exception as e:
        log_error_with_context(e, {"operation": "generate_final_report"})
        return {"status": "error", "report": format_error_for_user(e, "generating report")}


def generate_pdf_report_tool(state: AgentState) -> Dict[str, Any]:
    """
    Tool: Generate PDF report from final report text and save to disk.
    Returns the file path where PDF is saved.
    Includes comprehensive error handling.
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
        from reportlab.lib.enums import TA_LEFT, TA_CENTER
        
        # Get report content
        final_report = state.get("final_report", "")
        if not final_report:
            return {"status": "error", "message": "No final report available"}
        
        # Create reports directory if it doesn't exist
        reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        
        # Generate filename with visit_id
        visit_id = state.get("visit_id", str(uuid.uuid4()))
        pdf_filename = f"report_{visit_id}.pdf"
        pdf_path = os.path.join(reports_dir, pdf_filename)
        
        # Create PDF document
        doc = SimpleDocTemplate(pdf_path, pagesize=letter,
                              rightMargin=72, leftMargin=72,
                              topMargin=72, bottomMargin=18)
        
        # Container for PDF content
        story = []
        
        # Define styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor='#003366',
            spaceAfter=30,
            alignment=TA_CENTER
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor='#0066CC',
            spaceAfter=12,
            spaceBefore=12
        )
        normal_style = styles['Normal']
        
        # Add title
        story.append(Paragraph("Medical Diagnostic Report", title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Add patient information
        story.append(Paragraph("<b>Patient Information</b>", heading_style))
        patient_info = f"""
        <b>Name:</b> {state.get('patient_name', 'N/A')}<br/>
        <b>Age:</b> {state.get('patient_age', 'N/A')} years<br/>
        <b>Gender:</b> {state.get('patient_gender', 'N/A')}<br/>
        <b>Weight:</b> {state.get('patient_weight', 'N/A')} kg<br/>
        <b>Smoker:</b> {'Yes' if state.get('patient_smoker') else 'No'}<br/>
        <b>Visit ID:</b> {visit_id}<br/>
        <b>Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        story.append(Paragraph(patient_info, normal_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Add symptoms
        if state.get('symptoms'):
            story.append(Paragraph("<b>Symptoms</b>", heading_style))
            story.append(Paragraph(state.get('symptoms', ''), normal_style))
            story.append(Spacer(1, 0.2*inch))
        
        # Add test results
        test_results = []
        if state.get('xray_result'):
            test_results.append(f"<b>X-ray:</b> {json.dumps(state['xray_result']) if isinstance(state['xray_result'], dict) else state['xray_result']}")
        if state.get('spirometry_result'):
            test_results.append(f"<b>Spirometry:</b> {json.dumps(state['spirometry_result']) if isinstance(state['spirometry_result'], dict) else state['spirometry_result']}")
        if state.get('cbc_result'):
            test_results.append(f"<b>CBC:</b> {json.dumps(state['cbc_result']) if isinstance(state['cbc_result'], dict) else state['cbc_result']}")
        
        if test_results:
            story.append(Paragraph("<b>Test Results</b>", heading_style))
            for result in test_results:
                story.append(Paragraph(result, normal_style))
            story.append(Spacer(1, 0.2*inch))
        
        # Add diagnosis
        if state.get('diagnosis'):
            story.append(Paragraph("<b>Diagnosis</b>", heading_style))
            story.append(Paragraph(state.get('diagnosis', ''), normal_style))
            story.append(Spacer(1, 0.2*inch))
        
        # Add treatment plan
        if state.get('treatment_plan'):
            story.append(Paragraph("<b>Treatment Plan</b>", heading_style))
            for i, treatment in enumerate(state.get('treatment_plan', []), 1):
                story.append(Paragraph(f"{i}. {treatment}", normal_style))
            story.append(Spacer(1, 0.2*inch))
        
        # Add dosages
        if state.get('calculated_dosages'):
            story.append(Paragraph("<b>Medication Dosages</b>", heading_style))
            for med, dose_info in state.get('calculated_dosages', {}).items():
                dose_text = f"<b>{med.capitalize()}:</b> {dose_info.get('dose', 'N/A')} - {dose_info.get('frequency', 'N/A')}"
                if dose_info.get('notes'):
                    dose_text += f"<br/><i>Note: {dose_info.get('notes')}</i>"
                story.append(Paragraph(dose_text, normal_style))
            story.append(Spacer(1, 0.2*inch))
        
        # Add home remedies
        if state.get('home_remedies'):
            story.append(Paragraph("<b>Home Care Recommendations</b>", heading_style))
            for remedy in state.get('home_remedies', []):
                story.append(Paragraph(f"• {remedy}", normal_style))
            story.append(Spacer(1, 0.2*inch))
        
        # Add follow-up instructions
        if state.get('followup_instruction'):
            story.append(Paragraph("<b>Follow-up Instructions</b>", heading_style))
            story.append(Paragraph(state.get('followup_instruction', ''), normal_style))
            story.append(Spacer(1, 0.2*inch))
        
        # Add full report text
        story.append(PageBreak())
        story.append(Paragraph("<b>Complete Report</b>", heading_style))
        # Split report into paragraphs for better formatting
        report_paragraphs = final_report.split('\n\n')
        for para in report_paragraphs:
            if para.strip():
                story.append(Paragraph(para.replace('\n', '<br/>'), normal_style))
                story.append(Spacer(1, 0.1*inch))
        
        # Build PDF
        doc.build(story)
        
        # Verify PDF was created
        if not os.path.exists(pdf_path):
            raise PDFGenerationError("PDF file was not created successfully")
        
        logger.info(f"Successfully generated PDF report: {pdf_path}")
        
        # Return relative path for database storage
        relative_path = f"reports/{pdf_filename}"
        return {"status": "success", "pdf_path": relative_path, "absolute_path": pdf_path}
        
    except ImportError as e:
        logger.error(f"PDF library not available: {e}")
        raise PDFGenerationError("PDF generation library not installed. Please install reportlab.")
        
    except PermissionError as e:
        log_error_with_context(e, {"pdf_path": pdf_path if 'pdf_path' in locals() else "unknown"})
        raise PDFGenerationError(f"Permission denied when creating PDF: {str(e)}")
        
    except OSError as e:
        log_error_with_context(e, {"pdf_path": pdf_path if 'pdf_path' in locals() else "unknown"})
        raise PDFGenerationError(f"File system error when creating PDF: {str(e)}")
        
    except Exception as e:
        log_error_with_context(e, {"operation": "generate_pdf_report"})
        raise PDFGenerationError(f"Error generating PDF: {str(e)}")


def summarize_report_tool(state: AgentState) -> Dict[str, Any]:
    """
    Tool: Summarize full report into 2-3 lines for history storage.
    Includes error handling with fallback summary.
    """
    from ..core.error_handling import LLMError
    
    content = state.get("final_report") or state.get("diagnosis", "")
    
    if not content:
        return {"status": "success", "summary": "Visit completed."}
    
    messages = [
        {"role": "system", "content": "Summarize the medical visit into 2 concise sentences for history storage."},
        {"role": "user", "content": f"Visit details: {content}"}
    ]
    
    try:
        summary = call_groq_llm(messages)
        
        if not summary or not summary.strip():
            # Fallback summary
            diagnosis = state.get("diagnosis", "Medical consultation")
            return {"status": "success", "summary": f"Visit for {diagnosis}. Treatment plan provided."}
        
        return {"status": "success", "summary": summary}
        
    except LLMError as e:
        log_error_with_context(e, {"operation": "summarize_report"})
        # Generate fallback summary
        diagnosis = state.get("diagnosis", "Medical consultation")
        fallback_summary = f"Visit for {diagnosis}. Treatment plan provided."
        return {"status": "partial", "summary": fallback_summary}
        
    except Exception as e:
        log_error_with_context(e, {"operation": "summarize_report"})
        return {"status": "error", "summary": "Visit completed."}


def generate_visit_id_tool(state: AgentState) -> Dict[str, Any]:
    """Tool: Generate unique visit ID."""
    if state.get("visit_id"):
        return {"status": "success", "visit_id": state["visit_id"]}
    return {"status": "success", "visit_id": str(uuid.uuid4())}


@handle_database_error
def save_to_db_tool(state: AgentState, visit_summary: str) -> Dict[str, Any]:
    """Tool: Save visit data to database. Handles updates to existing records with comprehensive error handling."""
    try:
        from ..core.database import SessionLocal
        from ..db_models.patient import Patient
        from ..db_models.visit import Visit
        from ..db_models.diagnosis import Diagnosis
        from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
        
        db = None
        try:
            db = SessionLocal()
            # 1. Update Patient
            patient_id = state.get("patient_id")
            patient = None
            if patient_id:
                patient = db.query(Patient).filter(Patient.id == patient_id).first()
            
            if not patient:
                patient = Patient(
                    name=state.get("patient_name", "Unknown"),
                    age=state.get("patient_age"),
                    gender=state.get("patient_gender"),
                    smoker=state.get("patient_smoker", False),
                    chronic_conditions=state.get("patient_chronic_conditions"),
                    occupation=state.get("patient_occupation"),
                )
                db.add(patient)
                db.flush()
                patient_id = patient.id
            else:
                if state.get("patient_name"):
                    patient.name = state.get("patient_name")
                if state.get("patient_age") is not None:
                    patient.age = state.get("patient_age")
                if state.get("patient_gender"):
                    patient.gender = state.get("patient_gender")
                if state.get("patient_smoker") is not None:
                    patient.smoker = state.get("patient_smoker")
                if state.get("patient_chronic_conditions"):
                    patient.chronic_conditions = state.get("patient_chronic_conditions")
                if state.get("patient_occupation"):
                    patient.occupation = state.get("patient_occupation")

            # 2. Generate PDF Report (if final_report exists)
            pdf_path = None
            if state.get("final_report"):
                try:
                    pdf_result = generate_pdf_report_tool(state)
                    if pdf_result.get("status") == "success":
                        pdf_path = pdf_result.get("pdf_path")
                        logger.info(f"PDF report generated: {pdf_path}")
                    else:
                        logger.warning(f"PDF generation failed: {pdf_result.get('message', 'Unknown error')}")
                except PDFGenerationError as e:
                    logger.warning(f"PDF generation error (non-critical): {e}. Continuing without PDF.")
                    # Don't fail the entire save operation if PDF generation fails
                except Exception as e:
                    logger.warning(f"Unexpected error during PDF generation (non-critical): {e}. Continuing without PDF.")
            
            # 3. Update Visit
            visit_id_str = state.get("visit_id")
            visit = None
            if visit_id_str:
                visit = db.query(Visit).filter(Visit.visit_id == visit_id_str).first()
            
            if not visit:
                visit = Visit(
                    visit_id=visit_id_str,
                    patient_id=patient_id,
                    symptoms=state.get("symptoms"),
                    doctor_notes=state.get("doctor_note"),
                    emergency_flag=state.get("emergency_flag", False),
                    pdf_report_path=pdf_path
                )
                db.add(visit)
            else:
                visit.symptoms = state.get("symptoms")
                visit.doctor_notes = state.get("doctor_note")
                visit.diagnosis = state.get("diagnosis")
                if state.get("xray_result"): visit.xray_result = json.dumps(state["xray_result"])
                if state.get("spirometry_result"): visit.spirometry_result = json.dumps(state["spirometry_result"])
                if state.get("cbc_result"): visit.cbc_result = json.dumps(state["cbc_result"])
                if pdf_path: visit.pdf_report_path = pdf_path

            db.flush()

            # 4. Update Diagnosis
            if state.get("diagnosis"):
                diag = db.query(Diagnosis).filter(Diagnosis.visit_id == visit.id).first()
                if not diag:
                    diag = Diagnosis(
                        visit_id=visit.id,
                        diagnosis=state.get("diagnosis"),
                        treatment_plan=json.dumps(state.get("treatment_plan", [])),
                        followup_instruction=state.get("followup_instruction")
                    )
                    db.add(diag)
                else:
                    diag.diagnosis = state.get("diagnosis")
                    diag.treatment_plan = json.dumps(state.get("treatment_plan", []))
                    diag.followup_instruction = state.get("followup_instruction")

            db.commit()
            logger.info(f"Successfully saved visit {visit_id_str} to database")
            return {"status": "success", "patient_id": patient_id, "visit_id": visit_id_str}
            
        except IntegrityError as e:
            if db:
                db.rollback()
            log_error_with_context(e, {"visit_id": visit_id_str, "operation": "save_visit"})
            raise DatabaseIntegrityError(f"Data integrity error: {str(e)}")
            
        except OperationalError as e:
            if db:
                db.rollback()
            log_error_with_context(e, {"visit_id": visit_id_str, "operation": "save_visit"})
            raise DatabaseConnectionError(f"Database connection error: {str(e)}")
            
        except SQLAlchemyError as e:
            if db:
                db.rollback()
            log_error_with_context(e, {"visit_id": visit_id_str, "operation": "save_visit"})
            raise DatabaseError(f"Database error: {str(e)}")
            
        except Exception as e:
            if db:
                db.rollback()
            log_error_with_context(e, {"visit_id": visit_id_str, "operation": "save_visit"})
            raise DatabaseError(f"Unexpected database error: {str(e)}")
            
        finally:
            if db:
                db.close()
                
    except DatabaseError:
        raise  # Re-raise database errors
    except Exception as e:
        log_error_with_context(e, {"operation": "save_to_db_tool"})
        return {"status": "error", "message": format_error_for_user(e, "saving visit to database")}


def rag_treatment_planner_tool(state: AgentState) -> Dict[str, Any]:
    """
    Tool: Generate treatment plan using RAG.
    Ensures diagnosis and followup are strings.
    """
    test_results_text = format_test_results_for_llm(state)
    rag_query = f"Symptoms: {state.get('symptoms')}. History: {state.get('patient_chronic_conditions')}. Tests: {test_results_text}"
    
    rag_context = ""
    try:
        from .rag.rag_agent import get_rag_agent
        rag_agent = get_rag_agent()
        rag_context = rag_agent.retrieve_context(query=rag_query, k=5)
    except Exception as rag_err:
        logger.warning(f"RAG retrieval failed: {rag_err}")
        rag_context = "No specific medical guidelines retrieved."

    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert pulmonologist. Use the patient data and medical guidelines "
                "to produce an evidence-based diagnosis and treatment plan. "
                "Return ONLY valid JSON with keys: diagnosis (string), treatment_plan (array of strings), "
                "home_remedies (array of strings), followup_instruction (string). "
                "Base recommendations on test results when available."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Patient: {state.get('patient_name', 'Unknown')}, "
                f"{state.get('patient_age', '?')}yo {state.get('patient_gender', '')}\n"
                f"Data: {rag_query}\n\n"
                f"Medical guidelines (RAG):\n{rag_context}"
            ),
        },
    ]

    try:
        response = call_groq_llm(messages, temperature=0.2, json_mode=True)
        data = json.loads(response)

        plan = RAGTreatmentPlanOutput.model_validate(data)

        return {
            "status": "success",
            "diagnosis": plan.diagnosis,
            "treatment_plan": plan.treatment_plan,
            "home_remedies": plan.home_remedies,
            "followup_instruction": plan.followup_instruction,
        }
    except Exception as e:
        logger.warning(f"RAG treatment planner error: {e}")
        return {"status": "error", "diagnosis": "Pending", "treatment_plan": [], "home_remedies": [], "followup_instruction": ""}


def load_patient_profile_tool(state: AgentState) -> Dict[str, Any]:
    patient_id = state.get("patient_id")
    if not patient_id:
        return {"status": "no_patient"}

    try:
        from ..core.database import SessionLocal
        from ..db_models.patient import Patient

        db = SessionLocal()
        try:
            patient = db.query(Patient).filter(Patient.id == patient_id).first()
            if not patient:
                return {"status": "not_found"}
            has_profile = bool(patient.name and patient.age is not None)
            return {
                "status": "success",
                "has_profile": has_profile,
                "name": patient.name,
                "age": patient.age,
                "gender": patient.gender,
                "smoker": patient.smoker,
                "chronic_conditions": patient.chronic_conditions,
                "occupation": patient.occupation,
            }
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"load_patient_profile_tool error: {e}")
        return {"status": "error"}


def save_patient_profile_tool(state: AgentState) -> Dict[str, Any]:
    patient_id = state.get("patient_id")
    if not patient_id:
        return {"status": "no_patient"}

    try:
        from ..core.database import SessionLocal
        from ..db_models.patient import Patient

        db = SessionLocal()
        try:
            patient = db.query(Patient).filter(Patient.id == patient_id).first()
            if not patient:
                patient = Patient(
                    name=state.get("patient_name", "Unknown"),
                    age=state.get("patient_age"),
                    gender=state.get("patient_gender"),
                    smoker=state.get("patient_smoker", False),
                    chronic_conditions=state.get("patient_chronic_conditions"),
                    occupation=state.get("patient_occupation"),
                )
                db.add(patient)
                db.flush()
                state["patient_id"] = patient.id
                patient_id = patient.id

            if state.get("patient_name"):
                patient.name = state.get("patient_name")
            if state.get("patient_age") is not None:
                patient.age = state.get("patient_age")
            if state.get("patient_gender"):
                patient.gender = state.get("patient_gender")
            if state.get("patient_smoker") is not None:
                patient.smoker = state.get("patient_smoker")
            if state.get("patient_chronic_conditions"):
                patient.chronic_conditions = state.get("patient_chronic_conditions")
            if state.get("patient_occupation"):
                patient.occupation = state.get("patient_occupation")

            db.commit()
            return {"status": "success"}
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"save_patient_profile_tool error: {e}")
        return {"status": "error", "message": str(e)}


def merge_client_state_snapshot(state: AgentState, snapshot: Optional[Dict[str, Any]]) -> AgentState:
    if not snapshot or not isinstance(snapshot, dict):
        return state

    merge_keys = (
        "patient_data_confirmed", "doctor_note", "tests_recommended", "symptoms",
        "symptom_duration", "patient_name", "patient_age", "patient_gender",
        "patient_smoker", "patient_weight", "emergency_checked", "emergency_flag",
        "missing_tests", "current_step",
    )
    for key in merge_keys:
        client_val = snapshot.get(key)
        if client_val is None:
            continue
        if isinstance(client_val, (list, dict)) and not client_val:
            continue
        server_val = state.get(key)
        if server_val is None or server_val is False or server_val == [] or server_val == {}:
            state[key] = client_val

    client_conv = snapshot.get("conversation_history") or []
    server_conv = state.get("conversation_history") or []
    if isinstance(client_conv, list) and client_conv:
        client_has_assistant = any(m.get("role") == "assistant" for m in client_conv if isinstance(m, dict))
        server_has_assistant = any(m.get("role") == "assistant" for m in server_conv if isinstance(m, dict))
        if client_has_assistant and not server_has_assistant:
            state["conversation_history"] = client_conv
        elif len(client_conv) > len(server_conv):
            state["conversation_history"] = client_conv

    client_step = snapshot.get("current_step")
    server_step = state.get("current_step")
    if client_step and (
        not server_step
        or (
            server_step == "patient_intake_waiting_input"
            and client_step in ("patient_intake_awaiting_confirmation", "patient_intake_complete")
        )
    ):
        state["current_step"] = client_step

    return state


def hydrate_agent_state_from_patient(state: AgentState) -> AgentState:
    if state.get("_profile_hydrated"):
        return state

    profile = load_patient_profile_tool(state)
    if profile.get("status") == "success":
        if profile.get("name") and not state.get("patient_name"):
            state["patient_name"] = profile["name"]
        if profile.get("age") is not None and state.get("patient_age") is None:
            state["patient_age"] = profile["age"]
        if profile.get("gender") and not state.get("patient_gender"):
            state["patient_gender"] = profile["gender"]
        if profile.get("smoker") is not None and state.get("patient_smoker") is None:
            state["patient_smoker"] = profile["smoker"]
        if profile.get("chronic_conditions") and not state.get("patient_chronic_conditions"):
            state["patient_chronic_conditions"] = profile["chronic_conditions"]
        if profile.get("occupation") and not state.get("patient_occupation"):
            state["patient_occupation"] = profile["occupation"]
        if profile.get("has_profile"):
            state["returning_patient_profile"] = True

    state["_profile_hydrated"] = True
    return state


def fetch_patient_history_tool(state: AgentState) -> Dict[str, Any]:
    """Tool: Fetch last 3 visits for a patient from database."""
    patient_id = state.get("patient_id")
    if not patient_id: return {"status": "no_patient", "visits": [], "formatted_history": ""}
    
    try:
        from ..core.database import SessionLocal
        from ..db_models.visit import Visit
        from ..db_models.diagnosis import Diagnosis
        db = SessionLocal()
        try:
            visits_db = db.query(Visit).filter(Visit.patient_id == patient_id).order_by(Visit.created_at.desc()).limit(3).all()
            history_parts = []
            visits_data = []
            for v in visits_db:
                diag = db.query(Diagnosis).filter(Diagnosis.visit_id == v.id).first()
                d_str = diag.diagnosis if diag else "No diagnosis"
                history_parts.append(f"Visit on {v.created_at}: {d_str}")
                visits_data.append({"visit_id": v.visit_id, "diagnosis": d_str})
            return {"status": "success", "visits": visits_data, "formatted_history": "\n".join(history_parts)}
        finally:
            db.close()
    except Exception as e:
        print(f"Error fetching history: {e}")
        return {"status": "error", "visits": [], "formatted_history": ""}
