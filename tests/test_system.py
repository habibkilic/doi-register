import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.nlp_engine import AcademicNLPEngine
from backend.xml_handler import CrossrefXMLHandler
from backend.doi_service import DoiService
from backend.payment_service import PaymentService

client = TestClient(app)


def test_nlp_engine_training_and_evaluation():
    engine = AcademicNLPEngine()
    assert engine.classifier is not None
    assert engine.vectorizer is not None

    sample_text = (
        "Bu dergi açık erişimli ve hakemli uluslararası bir bilimsel dergidir. "
        "Tüm makaleler Creative Commons Alıntı (CC BY 4.0) Lisansı ile lisanslanmıştır. "
        "Yazarlar telif hakkını ellerinde tutarlar. "
        "Çift taraflı körleme (double-blind) hakemlik uygulanır. "
        "İnsan ve hayvan denekleri içeren araştırmalarda yetkili Etik Kurul Onay Belgesi şarttır. "
        "Dergimiz makale gönderme veya işlem için ücret (APC) talep etmemektedir. "
        "Editörler kurulu ve yayın kurulu üyelerimiz kurumsal unvanlarıyla sitede listelenmiştir. "
        "Yayınlanan tüm makaleler LOCKSS ve kurumsal dijital depolarda arşivlenmektedir. "
        "Aday makaleler iThenticate ile intihal taramasına tabi tutulur. "
        "Türkçe ve İngilizce özet ve anahtar kelimeler zorunludur. "
        "Yazarlar çıkar çatışması olmadığını beyan etmelidir. "
        "Kaynakça APA 7 formatına uygun olmalıdır. "
        "Yılda iki sayı düzenli olarak yayınlanmaktadır."
    )

    result = engine.evaluate_journal_text(sample_text)
    assert "overall_summary" in result
    assert "indices" in result

    indices = result["indices"]
    assert "DOAJ" in indices
    assert "TR_DIZIN" in indices
    assert "SCOPUS" in indices
    assert "WEB_OF_SCIENCE" in indices
    assert "COPERNICUS" in indices

    # Uygun bir metin olduğu için DOAJ ve TR Dizin skoru yüksek olmalıdır
    assert indices["DOAJ"]["score_percentage"] >= 70
    assert indices["TR_DIZIN"]["score_percentage"] >= 70


def test_xml_generation_and_validation():
    journal_info = {
        "name": "Mühendislik Bilimleri Dergisi",
        "issn": "2149-9999",
        "publisher": "Test Yayıncılık",
        "publication_year": 2026,
        "volume": "10",
        "issue": "1",
        "doi_prefix": "10.55555"
    }
    articles = [{
        "title": "Derin Öğrenme ile Anlamsal Analiz",
        "authors": "Ahmet Yılmaz, Ayşe Demir",
        "publication_year": 2026,
        "first_page": "1",
        "last_page": "15",
        "doi_suffix": "mbd.2026.10.1.001"
    }]

    xml_str = CrossrefXMLHandler.generate_xml(journal_info, articles)
    assert "<doi_batch" in xml_str
    assert "BATCH_" in xml_str
    assert "10.55555/mbd.2026.10.1.001" in xml_str

    is_valid, parsed, errors = CrossrefXMLHandler.parse_and_validate_xml(xml_str)
    assert is_valid is True
    assert len(errors) == 0
    assert parsed["journal_title"] == "Mühendislik Bilimleri Dergisi"
    assert len(parsed["articles"]) == 1
    assert parsed["articles"][0]["title"] == "Derin Öğrenme ile Anlamsal Analiz"


def test_doi_service_crossref_and_zenodo():
    art = {"title": "Test Paper", "publication_year": 2026, "volume": "1", "issue": "1"}
    journal = {"doi_prefix": "10.55555", "issn": "1234-5678"}

    res_crossref = DoiService.register_doi(art, journal, provider="crossref_sandbox")
    assert res_crossref["status"] == "success"
    assert "10.55555/" in res_crossref["doi"]

    res_zenodo = DoiService.register_doi(art, journal, provider="zenodo")
    assert res_zenodo["status"] == "success"
    assert "10.5072/zenodo." in res_zenodo["doi"]


def test_payment_service():
    res = PaymentService.process_iyzico_payment(
        package_id="pack_10",
        card_number="5890 0400 0000 0016",
        card_holder="Test User",
        expiry="12/28",
        cvv="123"
    )
    assert res["success"] is True
    assert res["tokens_added"] == 10
    assert "IYZ-" in res["reference_code"]


def test_api_routes():
    # Dashboard route
    res_dash = client.get("/")
    assert res_dash.status_code == 200

    # Evaluate API
    res_eval = client.post("/api/evaluate", json={
        "raw_text": "Dergimiz açık erişimlidir. Telif hakları yazara aittir. Çift kör hakemlik uygulanır."
    })
    assert res_eval.status_code == 200
    data = res_eval.json()
    assert "indices" in data


def test_reference_service_and_doi_resolution():
    from backend.reference_service import ReferenceService
    sample_ref = (
        "[1] Vaswani, A., Shazeer, N., Parmar, N. (2017). Attention is all you need. NeurIPS.\n"
        "[2] LeCun, Y., Bengio, Y., & Hinton, G. (2015). Deep learning. Nature, 521(7553), 436-444."
    )
    result = ReferenceService.process_citation_list(sample_ref)
    assert result["total_citations"] == 2
    assert "citations" in result
    assert len(result["citations"]) == 2


def test_academic_calculator_service():
    from backend.academic_tools import AcademicCalculatorService
    score = AcademicCalculatorService.calculate_score(
        index_type="TR_DIZIN",
        author_count=2,
        author_order=1,
        is_corresponding=True
    )
    assert score["base_points"] == 10
    assert score["calculated_uak_points"] == 8.0  # 10 * 0.8
    assert score["is_qualified_major"] is True


def test_authentication_routes():
    # Login sayfası get testi
    res_login_page = client.get("/login")
    assert res_login_page.status_code == 200
    assert "Akademisyen Girişi" in res_login_page.text

    # Hatalı giriş testi
    res_fail = client.post("/login", data={"email": "wrong@test.com", "password": "wrong"}, follow_redirects=False)
    assert res_fail.status_code == 200
    assert "Hatalı e-posta veya şifre" in res_fail.text

    # Başarılı giriş testi (Demo kullanıcı)
    res_success = client.post("/login", data={"email": "editor@akademikdergi.com", "password": "123"}, follow_redirects=False)
    assert res_success.status_code == 303
    assert "user_session" in res_success.headers.get("set-cookie", "")


def test_form_to_doi_endpoint():
    form_data = {
        "title": "Yapay Zeka Destekli Akademik Hakemlik ve Dergi Yönetimi",
        "authors": "Prof. Dr. Ahmet Yılmaz, Doç. Dr. Selin Kaya",
        "abstract": "Bu çalışma akademik dergilerde yapay zeka entegrasyonunu ele almaktadır.",
        "journal_name": "Bilişim ve Teknoloji Dergisi",
        "issn": "2602-1234",
        "volume": "14",
        "issue": "2",
        "publication_year": 2026,
        "first_page": "105",
        "last_page": "120",
        "provider": "crossref_sandbox"
    }
    res = client.post("/api/article/form-to-doi", json=form_data)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "10.55555/" in data["doi"]
    assert "generated_xml" in data


def test_xml_import_and_assign_endpoint():
    journal_info = {
        "name": "Mühendislik Bilimleri Dergisi",
        "issn": "2149-9999",
        "publisher": "Test Yayıncılık",
        "publication_year": 2026,
        "volume": "10",
        "issue": "1",
        "doi_prefix": "10.55555"
    }
    articles = [{
        "title": "Derin Öğrenme ile Anlamsal Analiz",
        "authors": "Ahmet Yılmaz, Ayşe Demir",
        "publication_year": 2026,
        "first_page": "1",
        "last_page": "15"
    }]
    xml_str = CrossrefXMLHandler.generate_xml(journal_info, articles)
    res = client.post("/api/xml/import-and-assign", json={
        "xml_content": xml_str,
        "provider": "crossref_sandbox"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "10.55555/" in data["assigned_articles"][0]["doi"]



    # Çıkış yap testi
    res_logout = client.get("/logout", follow_redirects=False)
    assert res_logout.status_code == 303
