import uuid
import datetime
from typing import Dict, Any


class PaymentService:
    """
    iyzico Sandbox (Kredi Kartı) ve Banka Havale/EFT ödeme yönetimi.
    Hocanın kayıtta belirttiği SaaS ticari bakiye modelini uygular.
    """

    TOKEN_PACKAGES = [
        {"id": "pack_3", "name": "Başlangıç Paketi", "tokens": 3, "price": 9.0, "currency": "USD", "price_try": 290.0},
        {"id": "pack_10", "name": "Standart Dergi Paketi", "tokens": 10, "price": 25.0, "currency": "USD", "price_try": 800.0},
        {"id": "pack_50", "name": "Yıllık Kurumsal Paket", "tokens": 50, "price": 100.0, "currency": "USD", "price_try": 3200.0}
    ]

    BANK_ACCOUNTS = [
        {"bank": "Ziraat Bankası", "iban": "TR12 0001 0000 1234 5678 9000 01", "holder": "Akademik DOI Hizmetleri A.Ş."},
        {"bank": "İş Bankası", "iban": "TR64 0006 4000 0012 3456 7890 02", "holder": "Akademik DOI Hizmetleri A.Ş."}
    ]

    @classmethod
    def process_iyzico_payment(
        cls,
        package_id: str,
        card_number: str,
        card_holder: str,
        expiry: str,
        cvv: str
    ) -> Dict[str, Any]:
        """
        iyzico Sandbox ödeme simülasyonu.
        """
        pkg = next((p for p in cls.TOKEN_PACKAGES if p["id"] == package_id), cls.TOKEN_PACKAGES[0])
        ref_code = f"IYZ-{uuid.uuid4().hex[:8].upper()}"

        # Test kartı veya geçerli uzunluk kontrolü
        clean_card = card_number.replace(" ", "").replace("-", "")
        if len(clean_card) < 15:
            return {
                "success": False,
                "message": "Geçersiz kart numarası. Lütfen en az 16 haneli test kartı giriniz.",
                "reference_code": None
            }

        return {
            "success": True,
            "message": f"iyzico Sandbox: {pkg['price_try']} TL tutarındaki ödeme başarıyla onaylandı.",
            "reference_code": ref_code,
            "tokens_added": pkg["tokens"],
            "amount_paid": pkg["price_try"],
            "currency": "TRY",
            "method": "iyzico_card",
            "timestamp": datetime.datetime.utcnow().isoformat()
        }

    @classmethod
    def create_wire_transfer_order(
        cls,
        package_id: str,
        sender_name: str
    ) -> Dict[str, Any]:
        """
        Banka Havalesi / EFT siparişi oluşturur.
        """
        pkg = next((p for p in cls.TOKEN_PACKAGES if p["id"] == package_id), cls.TOKEN_PACKAGES[0])
        ref_code = f"EFT-{uuid.uuid4().hex[:8].upper()}"

        return {
            "success": True,
            "message": "Havale bildiriminiz alındı. Ödeme teyidinden sonra krediniz tanımlanacaktır.",
            "reference_code": ref_code,
            "tokens_to_add": pkg["tokens"],
            "expected_amount": pkg["price_try"],
            "currency": "TRY",
            "bank_accounts": cls.BANK_ACCOUNTS,
            "method": "wire_transfer",
            "status": "pending_approval",
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
