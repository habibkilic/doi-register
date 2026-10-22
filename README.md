# Akademik Dergi İndeks Denetim ve DOI Yönetim Portalı

Bu proje, akademik dergilerin uluslararası ve ulusal indekslere (**DOAJ, TR Dizin, Scopus, Web of Science, Index Copernicus**) uygunluğunu **Doğal Dil İşleme (NLP)** ile denetleyen, **Crossref Schema 4.4.2** uyumlu XML üreten/doğrulayan ve **Crossref Sandbox & Zenodo REST API** üzerinden test DOI'si atayan uçtan uca bir akademik web otomasyon sistemidir.

---

## 🚀 Başlıca Modüller

1. **Çoklu İndeks & NLP Kriter Denetim Motoru (`backend/nlp_engine.py`):**
   - 5 büyük indeksin (~90 kural parametresi) semantik denetimi.
   - Paragraf ve cümle düzeyinde TF-IDF + Logistic Regression ve Cosine Similarity analizi.
   - Her indeks için ayrı ağırlıklı başarı yüzdesi (`%0 - %100`) ve eksiklik karnesi.
   - İnteraktif 5'li **Radar (Örümcek Ağı) Grafiği** ve kanıt metinleri.

2. **Crossref XML Yönetimi ve Doğrulama (`backend/xml_handler.py`):**
   - Crossref Schema 4.4.2 standartlarında XML yükleme.
   - Head (ID, timestamp, depositor) ve Body (dergi künyesi, yazarlar, sayfalar, DOI) eksik alan doğrulama.
   - Manuel makalelerden tek tıkla resmi Crossref XML çıktısı üretme.

3. **Çift Sağlayıcılı DOI Atama Motoru (`backend/doi_service.py`):**
   - **Crossref Sandbox (Testbed):** `test.crossref.org` standartlarında `10.55555/...` formatında DOI üretimi.
   - **Zenodo REST API Sandbox:** CERN altyapısı üzerinden `10.5072/zenodo....` formatında test DOI'si.
   - Tekli ve toplu (batch) DOI tescili ve karekodlu PDF Tescil Sertifikası.

4. **SaaS Kredi ve Ödeme Modülü (`backend/payment_service.py`):**
   - Bakiye sistemi (1 DOI Tescili = 1 Kredi).
   - **iyzico Sandbox:** Güvenli test kredi kartı ile anında token yükleme simülasyonu.
   - **Banka Havalesi / EFT:** IBAN bilgileri ve otomatik sipariş referans kodu üretimi.

5. **Akademik Araçlar ve Kaynakça Denetimi (`backend/reference_service.py` & `backend/academic_tools.py`):**
   - Canlı Crossref API ile otomatik atıf doğrulama, eksik DOI bulma ve APA 7 formatlama.
   - ÜAK Doçentlik ve YÖK Akademik Teşvik puan hesaplama modülü.

6. **Kullanıcı Girişi ve Oturum Yönetimi:**
   - E-posta/şifre ile akademisyen kaydı, oturum çerezleri (cookie) ve profil bazlı kredi yönetimi.

7. **Form-to-XML Otomatik Dönüştürücü:**
   - Kullanıcıların XML dosyası hazırlamadan doğrudan web formu doldurarak DOI alabilmesi; form verilerinin arka planda Crossref Schema 4.4.2 XML'e dönüştürülmesi.

---

## 🛠️ Kurulum ve Çalıştırma

### 1. Hızlı Başlatma (Windows)
Doğrudan proje klasöründeki `start.bat` dosyasına çift tıklayarak sistemi başlatabilirsiniz.

### 2. Terminal ile Çalıştırma
```powershell
# Sanal ortamı aktif et
.\.venv\Scripts\Activate.ps1

# Sunucuyu başlat
$env:PYTHONPATH="."
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Tarayıcınızdan **`http://127.0.0.1:8000`** adresine giderek sistemi kullanabilirsiniz.

---

## 🧪 Testleri Çalıştırma
Tüm NLP motoru, XML şeması, DOI servisleri, ödeme, kaynakça denetimi, ÜAK puanlama ve API rotaları otomatik testlerden geçmektedir:
```powershell
$env:PYTHONPATH="."
.\.venv\Scripts\python -m pytest -v tests\test_system.py
```
*(Sonuç: 10/10 PASSED - %100 Başarı)*
