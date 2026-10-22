class XmlDoiAssignRequest(BaseModel):
    xml_content: str
    provider: str = "crossref_sandbox"
    zenodo_token: Optional[str] = None


@app.post("/api/xml/import-and-assign")
async def api_xml_import_and_assign(req: XmlDoiAssignRequest, db: Session = Depends(get_db)):
    """
    Yüklenen Crossref XML dosyasını ayrıştırır, eksik veri kontrolü yapar,
    veritabanına kaydeder ve tek tıkla Crossref / Zenodo üzerinden DOI atar.
    Hocanın ses kaydındaki: 'XML'i yükle -> kontrol et -> DOI Al butonuna bas -> DOI gelsin' akışı.
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

    # Dergiyi bul veya oluştur
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

        # Makaleyi veritabanına ekle
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

        # DOI Atama Çağrısı
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

        # DOI İstek Logu
        doi_req = DoiRequest(
            article_id=db_art.id,
            provider=req.provider,
            status="success",
            response_doi=assigned_doi,
            response_log=doi_res["submission_log"]
        )
        db.add(doi_req)

        # Kullanıcı bakiyesinden 1 kredi düş
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
