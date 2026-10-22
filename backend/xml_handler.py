import time
import datetime
from typing import Dict, List, Any, Tuple
from xml.etree import ElementTree as ET


class CrossrefXMLHandler:
    """
    Crossref Schema 4.4.2 uyumlu XML oluşturucu, ayrıştırıcı ve doğrulayıcı.
    Hocanın ses kaydında tahtada gösterdiği Crossref XML yapısını birebir uygular.
    """

    @staticmethod
    def generate_xml(
        journal_info: Dict[str, Any],
        articles: List[Dict[str, Any]],
        depositor_name: str = "Akademik Portal Admin",
        depositor_email: str = "editor@dergi.org"
    ) -> str:
        """Verilen dergi ve makale listesi için geçerli bir Crossref XML üretir."""
        batch_id = f"BATCH_{int(time.time())}"
        timestamp = int(time.time())

        root = ET.Element("doi_batch", {
            "version": "4.4.2",
            "xmlns": "http://www.crossref.org/schema/4.4.2",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xsi:schemaLocation": "http://www.crossref.org/schema/4.4.2 http://www.crossref.org/schemas/crossref4.4.2.xsd"
        })

        # --- HEAD KISMI ---
        head = ET.SubElement(root, "head")
        ET.SubElement(head, "doi_batch_id").text = batch_id
        ET.SubElement(head, "timestamp").text = str(timestamp)
        depositor = ET.SubElement(head, "depositor")
        ET.SubElement(depositor, "depositor_name").text = depositor_name
        ET.SubElement(depositor, "email_address").text = depositor_email
        ET.SubElement(head, "registrant").text = journal_info.get("publisher", "Akademik Dergi Yayıncılık")

        # --- BODY KISMI ---
        body = ET.SubElement(root, "body")
        journal = ET.SubElement(body, "journal")

        # Journal Metadata
        j_meta = ET.SubElement(journal, "journal_metadata")
        ET.SubElement(j_meta, "full_title").text = journal_info.get("name", "Akademik Araştırmalar Dergisi")
        if journal_info.get("issn"):
            ET.SubElement(j_meta, "issn", {"media_type": "electronic"}).text = journal_info.get("issn")

        # Journal Issue (Cilt/Sayı)
        j_issue = ET.SubElement(journal, "journal_issue")
        pub_date = ET.SubElement(j_issue, "publication_date", {"media_type": "online"})
        ET.SubElement(pub_date, "year").text = str(journal_info.get("publication_year", datetime.datetime.now().year))
        j_volume = ET.SubElement(j_issue, "journal_volume")
        ET.SubElement(j_volume, "volume").text = str(journal_info.get("volume", "1"))
        ET.SubElement(j_issue, "issue").text = str(journal_info.get("issue", "1"))

        # Her Makale İçin Article Bloğu
        for idx, art in enumerate(articles, start=1):
            j_art = ET.SubElement(journal, "journal_article", {"publication_type": "full_text"})

            titles = ET.SubElement(j_art, "titles")
            ET.SubElement(titles, "title").text = art.get("title", f"Araştırma Makalesi {idx}")

            # Yazarlar (Contributors)
            contribs = ET.SubElement(j_art, "contributors")
            authors_raw = art.get("authors", "Dr. Yazar")
            author_list = [a.strip() for a in authors_raw.split(",") if a.strip()]

            for a_idx, author_name in enumerate(author_list):
                role = "first" if a_idx == 0 else "additional"
                p_name = ET.SubElement(contribs, "person_name", {"contributor_role": "author", "sequence": role})
                parts = author_name.split()
                if len(parts) > 1:
                    ET.SubElement(p_name, "given_name").text = " ".join(parts[:-1])
                    ET.SubElement(p_name, "surname").text = parts[-1]
                else:
                    ET.SubElement(p_name, "surname").text = author_name

            # Yayın Tarihi
            a_pub_date = ET.SubElement(j_art, "publication_date", {"media_type": "online"})
            ET.SubElement(a_pub_date, "year").text = str(art.get("publication_year", datetime.datetime.now().year))

            # Sayfa Numaraları
            pages = ET.SubElement(j_art, "pages")
            ET.SubElement(pages, "first_page").text = str(art.get("first_page", "1"))
            ET.SubElement(pages, "last_page").text = str(art.get("last_page", "15"))

            # DOI Verisi (DOI Data)
            doi_prefix = journal_info.get("doi_prefix", "10.55555")
            doi_suffix = art.get("doi_suffix", f"dergi.{art.get('publication_year', 2026)}.{art.get('volume', 1)}.{idx:03d}")
            full_doi = art.get("doi_number") or f"{doi_prefix}/{doi_suffix}"

            doi_data = ET.SubElement(j_art, "doi_data")
            ET.SubElement(doi_data, "doi").text = full_doi
            article_url = art.get("url") or f"{journal_info.get('website_url', 'https://dergipark.org.tr')}/article/{idx}"
            ET.SubElement(doi_data, "resource").text = article_url

        ET.indent(root, space="  ")
        return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")

    @staticmethod
    def parse_and_validate_xml(xml_content: str) -> Tuple[bool, Dict[str, Any], List[str]]:
        """
        Yüklenen bir Crossref XML dosyasını ayrıştırır, eksik alanları kontrol eder.
        Dönüş: (is_valid, parsed_data, errors_or_warnings)
        """
        errors = []
        parsed = {
            "batch_id": None,
            "timestamp": None,
            "depositor_email": None,
            "journal_title": None,
            "issn": None,
            "volume": None,
            "issue": None,
            "publication_year": None,
            "articles": []
        }

        try:
            # XML Namespace temizleme veya toleranslı okuma
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            return False, parsed, [f"Geçersiz XML Sözdizimi (Syntax Error): {str(e)}"]

        def find_text_any_ns(elem, tag_name):
            for child in elem.iter():
                if child.tag.endswith(tag_name) and child.text:
                    return child.text.strip()
            return None

        # 1. Head Denetimi
        head_elem = None
        for child in root:
            if child.tag.endswith("head"):
                head_elem = child
                break

        if head_elem is not None:
            parsed["batch_id"] = find_text_any_ns(head_elem, "doi_batch_id")
            parsed["timestamp"] = find_text_any_ns(head_elem, "timestamp")
            parsed["depositor_email"] = find_text_any_ns(head_elem, "email_address")
        else:
            errors.append("Zorunlu <head> bloğu bulunamadı.")

        if not parsed["depositor_email"]:
            errors.append("Depositor e-posta adresi eksik (<email_address>).")

        # 2. Journal Bilgileri
        parsed["journal_title"] = find_text_any_ns(root, "full_title")
        if not parsed["journal_title"]:
            errors.append("Dergi tam adı bulunamadı (<full_title>).")

        parsed["issn"] = find_text_any_ns(root, "issn")
        parsed["volume"] = find_text_any_ns(root, "volume")
        parsed["issue"] = find_text_any_ns(root, "issue")
        parsed["publication_year"] = find_text_any_ns(root, "year")

        # 3. Makalelerin Tespiti
        for elem in root.iter():
            if elem.tag.endswith("journal_article"):
                art_data = {
                    "title": find_text_any_ns(elem, "title"),
                    "authors": [],
                    "year": find_text_any_ns(elem, "year") or parsed["publication_year"],
                    "first_page": find_text_any_ns(elem, "first_page"),
                    "last_page": find_text_any_ns(elem, "last_page"),
                    "doi": find_text_any_ns(elem, "doi"),
                    "resource_url": find_text_any_ns(elem, "resource")
                }

                # Yazarları topla
                for p_name in elem.iter():
                    if p_name.tag.endswith("person_name"):
                        g_name = find_text_any_ns(p_name, "given_name") or ""
                        s_name = find_text_any_ns(p_name, "surname") or ""
                        full_name = f"{g_name} {s_name}".strip()
                        if full_name:
                            art_data["authors"].append(full_name)

                if not art_data["title"]:
                    errors.append("Makalelerden birinde <title> alanı eksik.")
                if not art_data["authors"]:
                    errors.append(f"'{art_data['title'] or 'İsimsiz'}' makalesinde yazar (<person_name>) bilgisi eksik.")

                parsed["articles"].append(art_data)

        if not parsed["articles"]:
            errors.append("XML içinde hiç <journal_article> kaydı bulunamadı.")

        is_valid = len(errors) == 0
        return is_valid, parsed, errors
