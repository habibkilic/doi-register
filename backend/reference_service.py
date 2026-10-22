import re
import urllib.parse
from typing import Dict, List, Any
import requests


class ReferenceService:
    """
    Akademik kaynakça denetimi, Crossref üzerinden eksik DOI çözümü
    ve atıf doğrulama servisi.
    """

    CROSSREF_API_URL = "https://api.crossref.org/works"

    @classmethod
    def parse_citations(cls, raw_text: str) -> List[str]:
        """Ham kaynakça metnini satır ve numaralandırma bazında tekil atıflara ayırır."""
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        citations = []
        current = ""

        for line in lines:
            # Numara ile başlıyorsa (örn: [1], 1., 1-)
            if re.match(r"^(\[\d+\]|\d+[\.\)])\s+", line):
                if current:
                    citations.append(current.strip())
                current = line
            else:
                if current:
                    current += " " + line
                else:
                    current = line

        if current:
            citations.append(current.strip())

        # Eğer hiç numaralandırma yoksa satır satır böl
        if len(citations) <= 1 and len(lines) > 1:
            citations = [l for l in lines if len(l) > 25]

        return [c for c in citations if len(c) > 20]

    @classmethod
    def verify_single_citation(cls, citation_text: str) -> Dict[str, Any]:
        """Tek bir kaynakçayı Crossref API üzerinden doğrular ve eksik DOI'sini bulur."""
        clean_text = re.sub(r"^(\[\d+\]|\d+[\.\)])\s+", "", citation_text).strip()

        # Kaynakçanın içinde zaten DOI var mı?
        existing_doi_match = re.search(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", citation_text)
        existing_doi = existing_doi_match.group(0) if existing_doi_match else None

        # Crossref API araması
        query_param = urllib.parse.quote(clean_text)
        url = f"{cls.CROSSREF_API_URL}?query.bibliographic={query_param}&rows=1"

        headers = {
            "User-Agent": "AcademicJournalComplianceTool/1.0 (mailto:editor@akademikdergi.com)"
        }

        try:
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("message", {}).get("items", [])
                if items:
                    item = items[0]
                    matched_doi = item.get("DOI")
                    matched_title = item.get("title", [""])[0] if item.get("title") else "Başlık Yok"
                    matched_container = item.get("container-title", [""])[0] if item.get("container-title") else "Dergi Belirtilmedi"
                    
                    # Yayın yılı
                    pub_year = None
                    issued = item.get("issued", {}).get("date-parts", [[]])[0]
                    if issued:
                        pub_year = issued[0]

                    # Yazarlar
                    authors = []
                    for auth in item.get("author", []):
                        g = auth.get("given", "")
                        f = auth.get("family", "")
                        authors.append(f"{g} {f}".strip())

                    # Eşleşme Güveni (Score)
                    api_score = item.get("score", 0.0)
                    is_confident = api_score > 30.0 or (existing_doi and matched_doi and existing_doi.lower() == matched_doi.lower())

                    # APA 7 Formatında Çıktı Oluşturma
                    author_str = ", ".join(authors[:3]) + (" vd." if len(authors) > 3 else "")
                    apa_citation = f"{author_str} ({pub_year or 't.y.'}). {matched_title}. {matched_container}."
                    if matched_doi:
                        apa_citation += f" https://doi.org/{matched_doi}"

                    return {
                        "original_text": citation_text,
                        "status": "verified" if is_confident else "uncertain",
                        "had_doi_originally": bool(existing_doi),
                        "existing_doi": existing_doi,
                        "resolved_doi": matched_doi,
                        "doi_url": f"https://doi.org/{matched_doi}" if matched_doi else None,
                        "matched_title": matched_title,
                        "matched_journal": matched_container,
                        "matched_year": pub_year,
                        "matched_authors": authors,
                        "apa_formatted": apa_citation,
                        "message": "DOI doğrulandı ve güncellendi." if (not existing_doi and matched_doi) else "Kayıt doğrulandı."
                    }
        except Exception as e:
            pass

        # Yedek / API cevapsız durumu
        return {
            "original_text": citation_text,
            "status": "unverified",
            "had_doi_originally": bool(existing_doi),
            "existing_doi": existing_doi,
            "resolved_doi": existing_doi,
            "doi_url": f"https://doi.org/{existing_doi}" if existing_doi else None,
            "matched_title": None,
            "matched_journal": None,
            "matched_year": None,
            "matched_authors": [],
            "apa_formatted": citation_text,
            "message": "Crossref'te doğrudan eşleşme bulunamadı veya bağlantı zaman aşımına uğradı."
        }

    @classmethod
    def process_citation_list(cls, raw_text: str) -> Dict[str, Any]:
        """Tüm kaynakça listesini işler, eksik DOI'leri tamamlar ve özet istatistik çıkarır."""
        citations = cls.parse_citations(raw_text)
        results = []
        found_missing_dois = 0
        verified_count = 0

        for cit in citations:
            res = cls.verify_single_citation(cit)
            if res["status"] == "verified":
                verified_count += 1
            if not res["had_doi_originally"] and res["resolved_doi"]:
                found_missing_dois += 1
            results.append(res)

        total = len(citations)
        accuracy_rate = round((verified_count / max(total, 1)) * 100, 1)

        return {
            "total_citations": total,
            "verified_count": verified_count,
            "missing_dois_resolved": found_missing_dois,
            "accuracy_rate": accuracy_rate,
            "citations": results
        }
