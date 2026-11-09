# =========================================================================
# 🚨 هشدار بسیار مهم امنیتی و تجاری (CRITICAL PAYMENT GATEWAY WARNING) 🚨
# =========================================================================
# هشدار: این ماژول کاملاً شبیه‌سازی (Mock) است و به هیچ درگاه بانکی واقعی وصل نیست.
# قبل از اتصال هرگونه دکمه‌ی UI یا ابزارهای پرداخت آنلاین در پرتال والدین یا اپلیکیشن
# دانش‌آموز به این endpoint ها، کدهای این ماژول باید با کلیدهای API واقعی (Merchant ID)
# زرین‌پال، سداد، یا ملت جایگزین و برنامه‌نویسی واقعی شوند.
# تحت هیچ شرایطی نباید این کدهای شبیه‌سازی در محیط پروداکشن به عنوان درگاه فعال معرفی شوند.
# =========================================================================

import abc
import os
import uuid
import time

# FIX F-B1: پرچم Mock — کل این ماژول شبیه‌سازی است؛ factory در پروداکشن بالا نمی‌آید (پایین).
IS_MOCK = True

class BasePaymentGateway(abc.ABC):
    @abc.abstractmethod
    def initiate_payment(self, amount: int, description: str, callback_url: str) -> tuple[str, str]:
        """
        Initiates a payment.
        Returns: (redirect_url, gateway_reference)
        """
        pass

    @abc.abstractmethod
    def verify_payment(self, gateway_reference: str, amount: int) -> tuple[bool, str]:
        """
        Verifies a payment.
        Returns: (success_boolean, tracking_code)
        """
        pass


class ZarinpalGateway(BasePaymentGateway):
    def initiate_payment(self, amount: int, description: str, callback_url: str) -> tuple[str, str]:
        authority = f"zp_ref_{uuid.uuid4().hex[:12]}"
        # Mock payment page redirect URL
        redirect_url = f"/finance/mock_payment_page?gateway=zarinpal&authority={authority}&amount={amount}&callback={callback_url}"
        return redirect_url, authority

    def verify_payment(self, gateway_reference: str, amount: int) -> tuple[bool, str]:
        # If amount ends in 99, simulate a failure for E2E testing
        if str(amount).endswith("99"):
            return False, ""
        tracking_code = f"TRK_ZP_{int(time.time())}"
        return True, tracking_code


class MellatGateway(BasePaymentGateway):
    def initiate_payment(self, amount: int, description: str, callback_url: str) -> tuple[str, str]:
        ref_id = f"mel_ref_{uuid.uuid4().hex[:12]}"
        redirect_url = f"/finance/mock_payment_page?gateway=mellat&authority={ref_id}&amount={amount}&callback={callback_url}"
        return redirect_url, ref_id

    def verify_payment(self, gateway_reference: str, amount: int) -> tuple[bool, str]:
        if str(amount).endswith("99"):
            return False, ""
        tracking_code = f"TRK_MEL_{int(time.time())}"
        return True, tracking_code


class SamanGateway(BasePaymentGateway):
    def initiate_payment(self, amount: int, description: str, callback_url: str) -> tuple[str, str]:
        token = f"sam_ref_{uuid.uuid4().hex[:12]}"
        redirect_url = f"/finance/mock_payment_page?gateway=saman&authority={token}&amount={amount}&callback={callback_url}"
        return redirect_url, token

    def verify_payment(self, gateway_reference: str, amount: int) -> tuple[bool, str]:
        if str(amount).endswith("99"):
            return False, ""
        tracking_code = f"TRK_SAM_{int(time.time())}"
        return True, tracking_code


# FIX F-B1: factory سخت‌گیرانه — بدون fallback ساکت، با نگهبان پروداکشن.
def get_payment_gateway(gateway_name: str) -> BasePaymentGateway:
    # Mock در پروداکشن = پول‌سازی با URL؛ fail-loud (کال‌بک هم مستقلاً همین گارد را دارد).
    if IS_MOCK and os.getenv("ENV", "development").lower() == "production":
        raise RuntimeError("Mock payment gateway must never run in production")
    gateways = {
        "zarinpal": ZarinpalGateway(),
        "mellat": MellatGateway(),
        "saman": SamanGateway()
    }
    if gateway_name is None or gateway_name.lower() not in gateways:
        raise ValueError(f"unknown payment gateway: {gateway_name!r}")
    return gateways[gateway_name.lower()]


# FIX F-B1: قرارداد بازنویسی آینده‌ی verify واقعی (زرین‌پال/سداد/ملت) با کال‌بک جدید:
#  ۱) وریفای فقط با (authority ذخیره‌شده، amount ذخیره‌شده) — هرگز ورودی کوئری کال‌بک.
#  ۲) وریفای واقعی تک‌مصرف است: پاسخ «قبلاً وریفای‌شده» را موفقیت حساب کن، چون بازیابی
#     تسخیر کهنه (کرش بین وریفای و ثبت نهایی) دوباره وریفای می‌زند و درگاهِ مصرف‌شده خطا می‌دهد.
#  ۳) خطای گذرا (تایم‌اوت/شبکه) باید exception بدهد نه False — تا کال‌بک 500 بدهد و پرداخت در
#     VERIFYING بماند و با reclaim دوباره تلاش شود؛ False یعنی شکست قطعی (پولی حرکت نکرده).
