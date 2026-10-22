import os
import json
import pickle
import re
from typing import Dict, List, Any, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics.pairwise import cosine_similarity

CORPUS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "training_corpus.json")
CRITERIA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "criteria.json")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
MODEL_PATH = os.path.join(MODEL_DIR, "nlp_classifier.pkl")
VEC_PATH = os.path.join(MODEL_DIR, "vectorizer.pkl")


class AcademicNLPEngine:
    """
    Akademik dergi metinlerini, kurallarını ve politikalarını
    paragraf ve cümle düzeyinde analiz eden NLP Motoru.
    """

    def __init__(self):
        self.vectorizer: TfidfVectorizer = None
        self.classifier: LogisticRegression = None
        self.criteria_db: Dict[str, Any] = {}
        self.load_criteria()
        self.ensure_model()

    def load_criteria(self):
        if os.path.exists(CRITERIA_PATH):
            with open(CRITERIA_PATH, "r", encoding="utf-8") as f:
                self.criteria_db = json.load(f)

    def train(self, corpus_path: str = CORPUS_PATH) -> Dict[str, Any]:
        """Eğitim korpusunu kullanarak TF-IDF + LogisticRegression modelini eğitir."""
        if not os.path.exists(corpus_path):
            raise FileNotFoundError(f"Eğitim korpusu bulunamadı: {corpus_path}")

        with open(corpus_path, "r", encoding="utf-8") as f:
            corpus = json.load(f)

        texts = [item["text"] for item in corpus]
        labels = [item["category"] for item in corpus]

        # TF-IDF Vektörleştirici (Unigram + Bigram, Türkçe/İngilizce uyumlu)
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=2500,
            sublinear_tf=True
        )
        X = self.vectorizer.fit_transform(texts)

        self.classifier = LogisticRegression(max_iter=300, C=1.5)
        self.classifier.fit(X, labels)

        # Modelleri kaydet
        os.makedirs(MODEL_DIR, exist_ok=True)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(self.classifier, f)
        with open(VEC_PATH, "wb") as f:
            pickle.dump(self.vectorizer, f)

        # Eğitim skorunu hesapla
        train_accuracy = self.classifier.score(X, labels)
        return {
            "status": "success",
            "samples_count": len(texts),
            "classes": list(self.classifier.classes_),
            "train_accuracy": round(float(train_accuracy) * 100, 2)
        }

    def ensure_model(self):
        """Kayıtlı modeli yükler, yoksa otomatik olarak eğitir."""
        if os.path.exists(MODEL_PATH) and os.path.exists(VEC_PATH):
            try:
                with open(MODEL_PATH, "rb") as f:
                    self.classifier = pickle.load(f)
                with open(VEC_PATH, "rb") as f:
                    self.vectorizer = pickle.load(f)
                return
            except Exception:
                pass
        self.train()

    def clean_text(self, text: str) -> str:
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def segment_units(self, raw_text: str) -> List[str]:
        """Metni hem paragraflara hem de cümlelere ayırarak anlamsal birimler (units) üretir."""
        units = []
        # 1. Paragraflar
        paras = [p.strip() for p in re.split(r'\n\s*\n|\r\n\s*\r\n', raw_text) if p.strip()]
        for p in paras:
            clean_p = self.clean_text(p)
            if len(clean_p) > 25:
                units.append(clean_p)

        # 2. Cümleler (Nokta, soru veya ünlemden sonraki ayrıştırma)
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', raw_text) if len(s.strip()) > 20]
        for s in sentences:
            clean_s = self.clean_text(s)
            if clean_s not in units:
                units.append(clean_s)

        if not units and len(raw_text.strip()) > 15:
            units = [self.clean_text(raw_text)]
        return units

    def classify_paragraph(self, paragraph: str) -> Tuple[str, float]:
        """Tek bir metin biriminin hangi kategoriye ait olduğunu ve güven skorunu döndürür."""
        if not self.classifier or not self.vectorizer:
            self.ensure_model()

        vec = self.vectorizer.transform([paragraph])
        probs = self.classifier.predict_proba(vec)[0]
        max_idx = int(np.argmax(probs))
        category = self.classifier.classes_[max_idx]
        confidence = float(probs[max_idx])
        return category, confidence

    def compute_semantic_similarity(self, text_a: str, text_b: str) -> float:
        """İki metin arasındaki TF-IDF Cosine benzerliğini hesaplar."""
        if not self.vectorizer:
            self.ensure_model()
        vecs = self.vectorizer.transform([text_a, text_b])
        sim = cosine_similarity(vecs[0:1], vecs[1:2])[0][0]
        return float(sim)

    def evaluate_journal_text(self, raw_text: str, index_keys: List[str] = None) -> Dict[str, Any]:
        """
        Dergi web sitesinden veya kılavuzundan alınan metni 5 indeks için
        paragraf, cümle ve kriter düzeyinde değerlendirir.
        """
        if index_keys is None:
            index_keys = ["DOAJ", "TR_DIZIN", "SCOPUS", "WEB_OF_SCIENCE", "COPERNICUS"]

        units = self.segment_units(raw_text)
        unit_analysis = []
        for u in units:
            cat, conf = self.classify_paragraph(u)
            unit_analysis.append({"text": u, "category": cat, "confidence": round(conf, 3)})

        full_text_lower = raw_text.lower()
        results_by_index = {}

        for idx_key in index_keys:
            if idx_key not in self.criteria_db:
                continue

            index_info = self.criteria_db[idx_key]
            criteria_list = index_info.get("criteria", [])
            total_weight = sum(c.get("weight", 1) for c in criteria_list)
            earned_weight = 0
            detailed_checks = []

            for crit in criteria_list:
                crit_id = crit["id"]
                crit_title = crit["title"]
                crit_cat = crit.get("category", "")
                crit_weight = crit.get("weight", 1)
                keywords = crit.get("keywords", [])

                # 1. Anahtar Kelime Uyumu (Keyword Density & Presence)
                matched_keywords = [kw for kw in keywords if kw.lower() in full_text_lower]
                kw_ratio = len(matched_keywords) / max(len(keywords), 1)

                # 2. NLP Kategori Eşleşmesi (Semantik Uygun Cümle/Paragraf Var mı?)
                matching_units = [u for u in unit_analysis if u["category"] == crit_cat and u["confidence"] > 0.20]
                has_semantic_match = len(matching_units) > 0
                best_confidence = max([u["confidence"] for u in matching_units], default=0.0)

                # 3. Semantik Benzerlik Skoru (Kriter açıklaması ile en iyi cümle arasındaki bağ)
                crit_desc = crit.get("description", "")
                best_sim = 0.0
                best_evidence = ""
                for u in units:
                    sim = self.compute_semantic_similarity(crit_desc, u)
                    if sim > best_sim:
                        best_sim = sim
                        best_evidence = u

                # Kriter Puanı Hesabı (Hibrit Model)
                nlp_score = (best_confidence * 0.6) + (min(best_sim * 2.2, 1.0) * 0.4)
                if has_semantic_match and len(matched_keywords) > 0:
                    nlp_score = max(nlp_score, 0.85)
                elif has_semantic_match:
                    nlp_score = max(nlp_score, 0.70)
                elif len(matched_keywords) > 0:
                    nlp_score = max(nlp_score, 0.65)

                item_score_ratio = (kw_ratio * 0.4) + (nlp_score * 0.6)
                is_passed = item_score_ratio >= 0.40

                earned_for_item = crit_weight if is_passed else (crit_weight * item_score_ratio)
                earned_weight += earned_for_item

                detailed_checks.append({
                    "id": crit_id,
                    "title": crit_title,
                    "category": crit_cat,
                    "weight": crit_weight,
                    "earned": round(earned_for_item, 2),
                    "passed": is_passed,
                    "score_percentage": round(min(item_score_ratio * 100, 100.0), 1),
                    "matched_keywords": matched_keywords,
                    "evidence_snippet": (best_evidence[:160] + "...") if best_evidence else "Metinde doğrudan kanıt bulunamadı.",
                    "recommendation": f"Web sitenizde '{crit_title}' ile ilgili açık ve detaylı bir politika paragrafı ekleyiniz." if not is_passed else "Kriter başarıyla sağlandı."
                })

            final_percentage = round((earned_weight / max(total_weight, 1)) * 100, 1)
            min_pass = index_info.get("min_pass_score", 70)

            results_by_index[idx_key] = {
                "name": index_info.get("name", idx_key),
                "score_percentage": min(final_percentage, 100.0),
                "status": "Uygun (Başvuruya Hazır)" if final_percentage >= min_pass else "Eksikler Var (Geliştirilmeli)",
                "passed_count": sum(1 for c in detailed_checks if c["passed"]),
                "total_count": len(detailed_checks),
                "min_pass_score": min_pass,
                "criteria_details": detailed_checks
            }

        return {
            "overall_summary": {
                "analyzed_units_count": len(units),
                "average_score": round(np.mean([res["score_percentage"] for res in results_by_index.values()]), 1),
                "indices_evaluated": list(results_by_index.keys())
            },
            "indices": results_by_index
        }
