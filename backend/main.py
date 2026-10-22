import os
import json
import uuid
import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.database import engine, Base, get_db, SessionLocal
from backend.models import User, Journal, Evaluation, Article, DoiRequest, TokenTransaction
from backend.nlp_engine import AcademicNLPEngine
from backend.xml_handler import CrossrefXMLHandler
from backend.doi_service import DoiService
from backend.payment_service import PaymentService
from backend.reference_service import ReferenceService
from backend.academic_tools import AcademicCalculatorService

# Veritabanı tablolarını oluştur
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Akademik Dergi Denetim ve DOI Yönetim Portalı", version="1.0.0")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "..", "frontend", "templates")
STATIC_DIR = os.path.join(BASE_DIR, "..", "frontend", "static")
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Global NLP Motoru başlatma
nlp_engine = AcademicNLPEngine()


import hashlib

# --- ŞİFRELEME VE GÜVENLİK YARDIMCILARI ---
def hash_password(password: str) -> str:
    return hashlib.sha256((password + "akademik_auth_salt_2026").encode("utf-8")).hexdigest()

def verify_password(password: str, hashed: Optional[str]) -> bool:
    if not hashed:
        return True
    return hash_password(password) == hashed


# Başlangıçta örnek demo kullanıcıları ve dergisi oluştur
def init_demo_data():
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(email="editor@akademikdergi.com").first()
        if not user:
            user = User(
                email="editor@akademikdergi.com",
                name="Prof. Dr. Ahmet Yılmaz",
                password_hash=hash_password("123"),
                academic_title="Prof. Dr.",
                institution="İstanbul Teknik Üniversitesi",
                token_balance=15
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            demo_journal = Journal(
                user_id=user.id,
                name="Uluslararası Fen ve Mühendislik Araştırmaları Dergisi",
                issn="2149-1234",
                e_issn="2149-5678",
                publisher="Akademik Yayıncılık Derneği",
                website_url="https://dergipark.org.tr/tr/pub/ufmad",
                doi_prefix="10.55555",
                description="Mühendislik, temel bilimler ve teknoloji alanlarında özgün araştırmalar yayınlayan uluslararası hakemli dergi."
            )
            db.add(demo_journal)
            db.commit()
            db.refresh(demo_journal)

            # Örnek makaleler ekle
            art1 = Article(
                journal_id=demo_journal.id,
                title="Yapay Zeka ve Doğal Dil İşleme Tabanlı Akademik İnceleme Sistemleri",
                authors="Dr. Zeynep Kaya, Doç. Dr. Mehmet Demir",
                abstract="Bu çalışmada modern doğal dil işleme algoritmaları kullanılarak dergi indeksleme kriterlerinin otomatik denetimi incelenmiştir.",
                volume="12",
                issue="2",
                publication_year=2026,
                first_page="101",
                last_page="118",
                doi_number="10.55555/ufmad.2026.12.2.001",
                status="registered"
            )
            art2 = Article(
                journal_id=demo_journal.id,
                title="Büyük Dil Modelleri ile Bilimsel Metin Sınıflandırma",
                authors="Ali Can, Prof. Dr. Ayşe Yıldız",
                abstract="Araştırmada akademik makalelerdeki metodoloji ve etik beyan paragraflarının tespiti için derin öğrenme modelleri karşılaştırılmıştır.",
                volume="12",
                issue="2",
                publication_year=2026,
                first_page="119",
                last_page="135",
                doi_number=None,
                status="pending"
            )
            db.add_all([art1, art2])
            db.commit()
        else:
            if not user.password_hash:
                user.password_hash = hash_password("123")
                db.commit()

        # İkinci demo kullanıcı: Yazar
        author_user = db.query(User).filter_by(email="yazar@akademikdergi.com").first()
        if not author_user:
            author_user = User(
                email="yazar@akademikdergi.com",
                name="Doç. Dr. Zeynep Kaya",
                password_hash=hash_password("123"),
                academic_title="Doç. Dr.",
                institution="Orta Doğu Teknik Üniversitesi",
                token_balance=10
            )
            db.add(author_user)
            db.commit()

    finally:
        db.close()


init_demo_data()


def get_current_user(first_arg=None, db: Session = Depends(get_db)) -> User:
    """
    Aktif oturumdaki kullanıcıyı cookie'den getirir; yoksa varsayılan editörü döner.
    first_arg bir Request veya Session nesnesi olabilir.
    """
    req = None
    session = None

    if isinstance(first_arg, Request):
        req = first_arg
    elif isinstance(first_arg, Session) or hasattr(first_arg, "query"):
        session = first_arg

    if session is None and hasattr(db, "query"):
        session = db

    close_session_after = False
    if session is None or not hasattr(session, "query"):
        session = SessionLocal()
        close_session_after = True

    try:
        user = None
        if req is not None and hasattr(req, "cookies"):
            user_id = req.cookies.get("user_session")
            if user_id:
                try:
                    user = session.query(User).filter_by(id=int(user_id)).first()
                except Exception:
                    pass
        if not user:
            user = session.query(User).filter_by(email="editor@akademikdergi.com").first()
        return user
    finally:
        if close_session_after:
            session.close()


# --- KİMLİK DOĞRULAMA ROTALARI (LOGIN, REGISTER, LOGOUT) ---

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error_message: Optional[str] = None):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error_message": error_message}
    )


@app.post("/login")
async def login_action(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter_by(email=email.strip().lower()).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error_message": "Hatalı e-posta veya şifre girdiniz. Lütfen tekrar deneyiniz."}
        )

    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="user_session", value=str(user.id), max_age=86400 * 7, httponly=True)
    return response


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, error_message: Optional[str] = None):
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={"error_message": error_message}
    )


@app.post("/register")
async def register_action(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    name: str = Form(...),
    academic_title: str = Form("Dr. Öğr. Üyesi"),
    institution: str = Form("Üniversite"),
    db: Session = Depends(get_db)
):
    clean_email = email.strip().lower()
    existing = db.query(User).filter_by(email=clean_email).first()
    if existing:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error_message": "Bu e-posta adresiyle kayıtlı bir hesap zaten var."}
        )

    new_user = User(
        email=clean_email,
        name=name.strip(),
        academic_title=academic_title,
        institution=institution.strip(),
        password_hash=hash_password(password),
        token_balance=10  # 10 Hediye DOI kredisi
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="user_session", value=str(new_user.id), max_age=86400 * 7, httponly=True)
    return response


@app.get("/logout")
async def logout_action():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="user_session")
    return response


# --- SAYFA ROTALARI (HTML TEMPLATES) ---

@app.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    journals = db.query(Journal).filter_by(user_id=user.id).all()
    articles = db.query(Article).all()
    evaluations = db.query(Evaluation).order_by(Evaluation.created_at.desc()).limit(5).all()

    registered_doi_count = sum(1 for a in articles if a.status == "registered")
    pending_doi_count = sum(1 for a in articles if a.status == "pending")

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "user": user,
            "journals": journals,
            "articles": articles,
            "evaluations": evaluations,
            "registered_doi_count": registered_doi_count,
            "pending_doi_count": pending_doi_count
        }
    )


@app.get("/evaluate", response_class=HTMLResponse)
async def evaluate_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    journals = db.query(Journal).filter_by(user_id=user.id).all()
    return templates.TemplateResponse(
        request=request,
        name="evaluate.html",
        context={
            "user": user,
            "journals": journals
        }
    )


@app.get("/doi", response_class=HTMLResponse)
async def doi_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    journals = db.query(Journal).filter_by(user_id=user.id).all()
    articles = db.query(Article).order_by(Article.created_at.desc()).all()
    return templates.TemplateResponse(
        request=request,
        name="doi_manager.html",
        context={
            "user": user,
            "journals": journals,
            "articles": articles
        }
    )


@app.get("/payment", response_class=HTMLResponse)
async def payment_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    packages = PaymentService.TOKEN_PACKAGES
    bank_accounts = PaymentService.BANK_ACCOUNTS
    transactions = db.query(TokenTransaction).filter_by(user_id=user.id).order_by(TokenTransaction.created_at.desc()).all()
    return templates.TemplateResponse(
        request=request,
        name="payment.html",
        context={
            "user": user,
            "packages": packages,
            "bank_accounts": bank_accounts,
            "transactions": transactions
        }
    )


@app.get("/tools", response_class=HTMLResponse)
async def academic_tools_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    index_options = AcademicCalculatorService.INDEX_SCORES
    return templates.TemplateResponse(
        request=request,
        name="academic_tools.html",
        context={
            "user": user,
            "index_options": index_options
        }
    )


# --- API UÇ NOKTALARI (REST API) ---

class EvaluateRequest(BaseModel):
    journal_id: Optional[int] = None
    raw_text: str
    indices: Optional[List[str]] = None


@app.post("/api/evaluate")
async def api_evaluate_journal(req: EvaluateRequest, db: Session = Depends(get_db)):
    if not req.raw_text.strip():
        raise HTTPException(status_code=400, detail="Analiz için metin içeriği girilmelidir.")

    selected_indices = req.indices or ["DOAJ", "TR_DIZIN", "SCOPUS", "WEB_OF_SCIENCE", "COPERNICUS"]
    result = nlp_engine.evaluate_journal_text(req.raw_text, selected_indices)

    # Veritabanına değerlendirme kaydı
    if req.journal_id:
        scores = result["indices"]
        eval_record = Evaluation(
            journal_id=req.journal_id,
            overall_score=result["overall_summary"]["average_score"],
            doaj_score=scores.get("DOAJ", {}).get("score_percentage", 0.0),
            tr_dizin_score=scores.get("TR_DIZIN", {}).get("score_percentage", 0.0),
            scopus_score=scores.get("SCOPUS", {}).get("score_percentage", 0.0),
            wos_score=scores.get("WEB_OF_SCIENCE", {}).get("score_percentage", 0.0),
            copernicus_score=scores.get("COPERNICUS", {}).get("score_percentage", 0.0),
            raw_text=req.raw_text[:2000],
            full_report_json=json.dumps(result, ensure_ascii=False)
        )
        db.add(eval_record)
        db.commit()

    return JSONResponse(content=result)


@app.post("/api/xml/upload")
async def api_upload_xml(xml_file: UploadFile = File(...)):
    content = await xml_file.read()
    xml_str = content.decode("utf-8", errors="ignore")
    is_valid, parsed, errors = CrossrefXMLHandler.parse_and_validate_xml(xml_str)
    return {
        "is_valid": is_valid,
        "parsed_data": parsed,
        "errors": errors,
        "article_count": len(parsed.get("articles", []))
    }


@app.post("/api/xml/generate")
async def api_generate_xml(
    journal_id: int = Form(...),
    db: Session = Depends(get_db)
):
    journal = db.query(Journal).filter_by(id=journal_id).first()
    if not journal:
        raise HTTPException(status_code=404, detail="Dergi bulunamadı.")

    articles = db.query(Article).filter_by(journal_id=journal.id).all()
    j_info = {
        "name": journal.name,
        "issn": journal.issn,
        "publisher": journal.publisher,
        "website_url": journal.website_url,
        "doi_prefix": journal.doi_prefix,
        "volume": "1",
        "issue": "1"
    }
    art_list = [{
        "title": a.title,
        "authors": a.authors,
        "publication_year": a.publication_year,
        "volume": a.volume,
        "issue": a.issue,
        "first_page": a.first_page,
        "last_page": a.last_page,
        "doi_number": a.doi_number
    } for a in articles]

    xml_content = CrossrefXMLHandler.generate_xml(j_info, art_list)
    return HTMLResponse(content=xml_content, media_type="application/xml")


class AssignDoiRequest(BaseModel):
    article_id: int
    provider: str = "crossref_sandbox"  # crossref_sandbox veya zenodo
    zenodo_token: Optional[str] = None


@app.post("/api/doi/assign")
async def api_assign_doi(req: AssignDoiRequest, db: Session = Depends(get_db)):
    user = get_current_user(db)
    if user.token_balance < 1:
        raise HTTPException(
            status_code=402,
            detail="Yetersiz Bakiye! DOI almak için lütfen 'Bakiye / Kredi Yükle' sayfasına gidiniz."
        )

    article = db.query(Article).filter_by(id=req.article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Makale bulunamadı.")

    journal = article.journal

    art_dict = {
        "title": article.title,
        "authors": article.authors,
        "abstract": article.abstract,
        "volume": article.volume,
        "issue": article.issue,
        "publication_year": article.publication_year,
        "first_page": article.first_page,
        "last_page": article.last_page
    }
    j_dict = {
        "name": journal.name,
        "issn": journal.issn,
        "doi_prefix": journal.doi_prefix
    }

    doi_result = DoiService.register_doi(
        article_data=art_dict,
        journal_data=j_dict,
        provider=req.provider,
        zenodo_token=req.zenodo_token
    )

    if doi_result.get("status") == "success":
        # Kredi düşümü
        user.token_balance -= 1

        article.doi_number = doi_result["doi"]
        article.status = "registered"

        # Log kaydı
        doi_req_record = DoiRequest(
            article_id=article.id,
            provider=req.provider,
            status="success",
            response_doi=doi_result["doi"],
            response_log=doi_result["submission_log"]
        )
        db.add(doi_req_record)
        db.commit()

        return {
            "success": True,
            "doi": doi_result["doi"],
            "doi_url": doi_result["doi_url"],
            "remaining_tokens": user.token_balance,
            "provider": doi_result["provider"],
            "log": doi_result["submission_log"]
        }
    else:
        raise HTTPException(status_code=500, detail="DOI atama işlemi başarısız oldu.")


class XmlDoiAssignRequest(BaseModel):
    xml_content: str
    provider: str = "crossref_sandbox"
    zenodo_token: Optional[str] = None


@app.post("/api/xml/import-and-assign")
async def api_xml_import_and_assign(req: XmlDoiAssignRequest, db: Session = Depends(get_db)):
    """
    Yüklenen Crossref XML dosyasındaki makaleleri sisteme ekler ve
    seçilen sağlayıcı (Crossref / Zenodo) üzerinden resmi test DOI'si atar.
    """
    user = get_current_user(db)
    is_valid, parsed, errors = CrossrefXMLHandler.parse_and_validate_xml(req.xml_content)

    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail=f"XML doğrulanamadı. Eksiklikler: {', '.join(errors)}"
        )

    articles_to_process = parsed.get("articles", [])
    article_count = len(articles_to_process)

    if article_count == 0:
        raise HTTPException(status_code=400, detail="XML içinde işlenecek makale bulunamadı.")

    if user.token_balance < article_count:
        raise HTTPException(
            status_code=402,
            detail=f"Yetersiz Bakiye! {article_count} makale için {article_count} kredi gerekli. Mevcut bakiyeniz: {user.token_balance} kredi."
        )

    journal_title = parsed.get("journal_title") or "Akademik Araştırmalar Dergisi"
    issn = parsed.get("issn") or "2149-5678"

    journal = db.query(Journal).filter_by(name=journal_title).first()
    if not journal:
        journal = Journal(
            user_id=user.id,
            name=journal_title,
            issn=issn,
            doi_prefix="10.55555",
            publisher=parsed.get("journal_title"),
            description="XML yüklemesi ile otomatik oluşturulan dergi kaydı."
        )
        db.add(journal)
        db.commit()
        db.refresh(journal)

    assigned_results = []

    for art_data in articles_to_process:
        title = art_data.get("title") or "Başlıksız Makale"
        authors_list = art_data.get("authors", ["Yazar"])
        authors_str = ", ".join(authors_list) if isinstance(authors_list, list) else str(authors_list)
        year = int(art_data.get("year") or parsed.get("publication_year") or datetime.datetime.now().year)
        vol = str(parsed.get("volume") or "1")
        issue = str(parsed.get("issue") or "1")

        db_art = Article(
            journal_id=journal.id,
            title=title,
            authors=authors_str,
            publication_year=year,
            volume=vol,
            issue=issue,
            first_page=art_data.get("first_page") or "1",
            last_page=art_data.get("last_page") or "10",
            status="pending"
        )
        db.add(db_art)
        db.commit()
        db.refresh(db_art)

        doi_res = DoiService.register_doi(
            article_data={
                "title": title,
                "authors": authors_str,
                "publication_year": year,
                "volume": vol,
                "issue": issue
            },
            journal_data={
                "name": journal.name,
                "issn": journal.issn,
                "doi_prefix": journal.doi_prefix
            },
            provider=req.provider,
            zenodo_token=req.zenodo_token
        )

        assigned_doi = doi_res["doi"]
        db_art.doi_number = assigned_doi
        db_art.status = "registered"

        doi_req = DoiRequest(
            article_id=db_art.id,
            provider=req.provider,
            status="success",
            response_doi=assigned_doi,
            response_log=doi_res["submission_log"]
        )
        db.add(doi_req)
        user.token_balance -= 1

        assigned_results.append({
            "article_id": db_art.id,
            "title": title,
            "authors": authors_str,
            "doi": assigned_doi,
            "doi_url": doi_res["doi_url"],
            "provider": doi_res["provider"]
        })

    db.commit()

    return {
        "success": True,
        "message": f"Tebrikler! {len(assigned_results)} adet makale için DOI başarıyla üretildi.",
        "remaining_tokens": user.token_balance,
        "assigned_articles": assigned_results
    }


class FormDoiRequest(BaseModel):
    journal_name: str
    issn: Optional[str] = "2149-5678"
    doi_prefix: Optional[str] = "10.55555"
    publisher: Optional[str] = "Akademik Yayıncılık"
    title: str
    authors: str
    abstract: Optional[str] = ""
    publication_year: Optional[int] = datetime.datetime.now().year
    volume: Optional[str] = "1"
    issue: Optional[str] = "1"
    first_page: Optional[str] = "1"
    last_page: Optional[str] = "15"
    provider: Optional[str] = "crossref_sandbox"
    zenodo_token: Optional[str] = None


@app.post("/api/article/form-to-doi")
async def api_form_to_doi(req: FormDoiRequest, db: Session = Depends(get_db)):
    """
    Kullanıcının formdan doldurduğu bilgileri alır,
    arka planda Crossref Schema 4.4.2 uyumlu XML'e dönüştürür,
    şemayı doğrular, kaydeder ve doğrudan Crossref/Zenodo üzerinden DOI atar.
    """
    user = get_current_user(db)
    if user.token_balance < 1:
        raise HTTPException(
            status_code=402,
            detail=f"Yetersiz Bakiye! DOI almak için en az 1 krediniz olmalıdır. Mevcut bakiye: {user.token_balance} kredi."
        )

    if not req.journal_name.strip() or not req.title.strip() or not req.authors.strip():
        raise HTTPException(
            status_code=400,
            detail="Dergi Adı, Makale Başlığı ve Yazar alanları zorunludur."
        )

    # 1. Arka planda Crossref XML üretimi
    journal_info = {
        "name": req.journal_name.strip(),
        "issn": req.issn.strip() if req.issn else "2149-5678",
        "publisher": req.publisher.strip() if req.publisher else "Akademik Yayıncılık",
        "publication_year": req.publication_year or datetime.datetime.now().year,
        "volume": req.volume or "1",
        "issue": req.issue or "1",
        "doi_prefix": req.doi_prefix or "10.55555"
    }

    articles_data = [{
        "title": req.title.strip(),
        "authors": req.authors.strip(),
        "publication_year": req.publication_year or datetime.datetime.now().year,
        "volume": req.volume or "1",
        "issue": req.issue or "1",
        "first_page": req.first_page or "1",
        "last_page": req.last_page or "15"
    }]

    generated_xml = CrossrefXMLHandler.generate_xml(journal_info, articles_data)

    # 2. Üretilen XML'in Şema Doğrulaması
    is_valid, parsed, errors = CrossrefXMLHandler.parse_and_validate_xml(generated_xml)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Oluşturulan XML doğrulanamadı: {', '.join(errors)}")

    # 3. Dergiyi bul veya oluştur
    journal = db.query(Journal).filter_by(name=req.journal_name.strip()).first()
    if not journal:
        journal = Journal(
            user_id=user.id,
            name=req.journal_name.strip(),
            issn=req.issn.strip() if req.issn else "2149-5678",
            doi_prefix=req.doi_prefix or "10.55555",
            publisher=req.publisher.strip() if req.publisher else "Akademik Yayıncılık",
            description="Kullanıcı formu ile otomatik oluşturulan dergi."
        )
        db.add(journal)
        db.commit()
        db.refresh(journal)

    # 4. Makaleyi veritabanına ekle
    db_art = Article(
        journal_id=journal.id,
        title=req.title.strip(),
        authors=req.authors.strip(),
        abstract=req.abstract.strip() if req.abstract else None,
        publication_year=req.publication_year or datetime.datetime.now().year,
        volume=req.volume or "1",
        issue=req.issue or "1",
        first_page=req.first_page or "1",
        last_page=req.last_page or "15",
        status="pending"
    )
    db.add(db_art)
    db.commit()
    db.refresh(db_art)

    # 5. DOI Atama
    doi_res = DoiService.register_doi(
        article_data={
            "title": req.title.strip(),
            "authors": req.authors.strip(),
            "publication_year": req.publication_year or datetime.datetime.now().year,
            "volume": req.volume or "1",
            "issue": req.issue or "1"
        },
        journal_data={
            "name": journal.name,
            "issn": journal.issn,
            "doi_prefix": journal.doi_prefix
        },
        provider=req.provider or "crossref_sandbox",
        zenodo_token=req.zenodo_token
    )

    assigned_doi = doi_res["doi"]
    db_art.doi_number = assigned_doi
    db_art.status = "registered"

    doi_req = DoiRequest(
        article_id=db_art.id,
        provider=req.provider or "crossref_sandbox",
        status="success",
        response_doi=assigned_doi,
        response_log=doi_res["submission_log"]
    )
    db.add(doi_req)
    user.token_balance -= 1
    db.commit()

    return {
        "success": True,
        "message": "Form bilgileri başarıyla Crossref XML'e dönüştürüldü ve resmi test DOI'si atandı!",
        "doi": assigned_doi,
        "doi_url": doi_res["doi_url"],
        "provider": doi_res["provider"],
        "remaining_tokens": user.token_balance,
        "article_id": db_art.id,
        "title": req.title.strip(),
        "authors": req.authors.strip(),
        "generated_xml": generated_xml
    }


class CardPaymentRequest(BaseModel):
    package_id: str
    card_number: str
    card_holder: str
    expiry: str
    cvv: str


@app.post("/api/payment/card")
async def api_pay_card(req: CardPaymentRequest, db: Session = Depends(get_db)):
    user = get_current_user(db)
    result = PaymentService.process_iyzico_payment(
        package_id=req.package_id,
        card_number=req.card_number,
        card_holder=req.card_holder,
        expiry=req.expiry,
        cvv=req.cvv
    )

    if result["success"]:
        user.token_balance += result["tokens_added"]
        tx = TokenTransaction(
            user_id=user.id,
            tokens=result["tokens_added"],
            amount_paid=result["amount_paid"],
            currency=result["currency"],
            payment_method="iyzico_card",
            status="completed",
            reference_code=result["reference_code"]
        )
        db.add(tx)
        db.commit()

        return {
            "success": True,
            "message": result["message"],
            "new_balance": user.token_balance,
            "reference_code": result["reference_code"]
        }
    else:
        raise HTTPException(status_code=400, detail=result["message"])


class WireTransferRequest(BaseModel):
    package_id: str
    sender_name: str


@app.post("/api/payment/wire")
async def api_pay_wire(req: WireTransferRequest, db: Session = Depends(get_db)):
    user = get_current_user(db)
    result = PaymentService.create_wire_transfer_order(
        package_id=req.package_id,
        sender_name=req.sender_name
    )

    tx = TokenTransaction(
        user_id=user.id,
        tokens=result["tokens_to_add"],
        amount_paid=result["expected_amount"],
        currency=result["currency"],
        payment_method="wire_transfer",
        status="pending_approval",
        reference_code=result["reference_code"]
    )
    db.add(tx)
    db.commit()

    return result


class ReferencesCheckRequest(BaseModel):
    raw_references: str


@app.post("/api/references/check")
async def api_check_references(req: ReferencesCheckRequest):
    """
    Akademik kaynakçaları Crossref API ile tarar, eksik DOI'leri bulur,
    atıfların doğruluğunu denetler ve APA 7 formatında standartlaştırır.
    """
    if not req.raw_references.strip():
        raise HTTPException(status_code=400, detail="Lütfen kontrol edilecek kaynakçaları giriniz.")

    result = ReferenceService.process_citation_list(req.raw_references)
    return JSONResponse(content=result)


class AcademicScoreRequest(BaseModel):
    index_type: str
    author_count: int = 1
    author_order: int = 1
    is_corresponding: bool = False
    field: str = "engineering"


@app.post("/api/academic/calculate-score")
async def api_calculate_academic_score(req: AcademicScoreRequest):
    """
    ÜAK Doçentlik ve YÖK Akademik Teşvik puanını hesaplar.
    """
    result = AcademicCalculatorService.calculate_score(
        index_type=req.index_type,
        author_count=req.author_count,
        author_order=req.author_order,
        is_corresponding=req.is_corresponding,
        field=req.field
    )
    return JSONResponse(content=result)
