from typing import Dict, Any, List


class AcademicCalculatorService:
    """
    ÜAK Doçentlik Kriterleri ve Akademik Teşvik Puanı Hesaplama Servisi.
    Türkiye'deki güncel ÜAK (Üniversitelerarası Kurul) doçentlik yönetmeliğine dayanır.
    """

    INDEX_SCORES = {
        "WOS_Q1": {"name": "Web of Science (SCI/SSCI/AHCI) - Q1", "base_points": 30, "incentive_base": 30.0},
        "WOS_Q2": {"name": "Web of Science (SCI/SSCI/AHCI) - Q2", "base_points": 20, "incentive_base": 24.0},
        "WOS_Q3": {"name": "Web of Science (SCI/SSCI/AHCI) - Q3", "base_points": 15, "incentive_base": 18.0},
        "WOS_Q4_ESCI": {"name": "Web of Science (Q4) veya ESCI", "base_points": 10, "incentive_base": 12.0},
        "SCOPUS": {"name": "Scopus / Uluslararası Alan İndeksi", "base_points": 10, "incentive_base": 12.0},
        "TR_DIZIN": {"name": "TR Dizin (TÜBİTAK ULAKBİM)", "base_points": 10, "incentive_base": 12.0},
        "OTHER_REFEREED": {"name": "Diğer Hakemli Ulusal / Uluslararası Dergi", "base_points": 4, "incentive_base": 6.0}
    }

    @classmethod
    def calculate_score(
        cls,
        index_type: str,
        author_count: int = 1,
        author_order: int = 1,
        is_corresponding: bool = False,
        field: str = "engineering"
    ) -> Dict[str, Any]:
        """
        ÜAK Doçentlik ve YÖK Akademik Teşvik puanını hesaplar.
        """
        index_data = cls.INDEX_SCORES.get(index_type, cls.INDEX_SCORES["TR_DIZIN"])
        base_points = index_data["base_points"]
        incentive_base = index_data["incentive_base"]

        # Yazar Payı Çarpanı (ÜAK Formülü)
        if author_count == 1:
            multiplier = 1.0
            author_role_desc = "Tek Yazar (%100 Pay)"
        elif author_count == 2:
            if author_order == 1 or is_corresponding:
                multiplier = 0.8
                author_role_desc = "Başyazar / Sorumlu Yazar (%80 Pay)"
            else:
                multiplier = 0.5
                author_role_desc = "İkinci Yazar (%50 Pay)"
        else:
            # 3 veya daha fazla yazar
            if author_order == 1 or is_corresponding:
                multiplier = 0.6
                author_role_desc = "Başyazar / Sorumlu Yazar (%60 Pay)"
            else:
                multiplier = 0.4 / (author_count - 1)
                author_role_desc = f"{author_order}. Yazar (Paylaştırılmış)"

        uak_points = round(base_points * multiplier, 2)

        # Akademik Teşvik Katsayısı (Kişi sayısına göre azalan teşvik katsayısı)
        incentive_coeff = 1.0 / (author_count ** 0.5)
        incentive_points = round(incentive_base * incentive_coeff, 2)

        # Doçentlik Asgari Şart Uygunluk Değerlendirmesi
        is_qualified_major = index_type in ["WOS_Q1", "WOS_Q2", "WOS_Q3", "WOS_Q4_ESCI", "TR_DIZIN"]
        evaluation_note = (
            "✅ Bu yayın ÜAK Doçentlik asgari başvuru şartlarında (Madde 1/a veya 1/b) doğrudan geçerlidir."
            if is_qualified_major else
            "ℹ️ Bu yayın diğer uluslararası/ulusal kategorisinden ek puan olarak değerlendirilebilir."
        )

        return {
            "index_name": index_data["name"],
            "base_points": base_points,
            "author_count": author_count,
            "author_role": author_role_desc,
            "calculated_uak_points": uak_points,
            "calculated_incentive_points": incentive_points,
            "is_qualified_major": is_qualified_major,
            "evaluation_note": evaluation_note
        }
