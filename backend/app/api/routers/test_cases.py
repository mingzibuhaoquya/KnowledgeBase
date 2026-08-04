from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import KnowledgeDocument, TestCaseDraft
from app.schemas import GenerateCasesRequest, TestCaseDraftOut, TestCaseDraftUpdate
from app.services.case_generator import case_generator

router = APIRouter(prefix="/test-cases", tags=["test-cases"])


@router.post("/generate/{document_id}", response_model=list[TestCaseDraftOut])
def generate_cases(
    document_id: int,
    payload: GenerateCasesRequest,
    db: Session = Depends(get_db),
) -> list[TestCaseDraft]:
    document = db.get(KnowledgeDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="document not found")

    cases = case_generator.generate(document, payload.max_cases)
    db.add_all(cases)
    db.commit()
    for case in cases:
        db.refresh(case)
    return cases


@router.get("/document/{document_id}", response_model=list[TestCaseDraftOut])
def list_cases(document_id: int, db: Session = Depends(get_db)) -> list[TestCaseDraft]:
    return list(
        db.scalars(
            select(TestCaseDraft)
            .where(TestCaseDraft.document_id == document_id)
            .order_by(TestCaseDraft.created_at.asc())
        )
    )


@router.put("/{case_id}", response_model=TestCaseDraftOut)
def update_case(case_id: int, payload: TestCaseDraftUpdate, db: Session = Depends(get_db)) -> TestCaseDraft:
    case = db.get(TestCaseDraft, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="test case not found")
    for key, value in payload.model_dump().items():
        setattr(case, key, value)
    db.commit()
    db.refresh(case)
    return case

