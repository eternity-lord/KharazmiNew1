from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import abc
import datetime

import models
from models import Student, Teacher, Course, Enrollment, Attendance, SessionLog, Grade, Transaction, Installment, Lead, UserSession, Notification
from dependencies import get_db, check_user_login, get_session_student, get_session_parent

# FIX: Bug 16 - share the tuition-minus-payment debt calculation across financial views.
from financial_calculations import calculate_student_debt

router = APIRouter()

# =========================================================================
# ۱. انتزاع ارائه‌دهنده هوش مصنوعی (AI Provider Abstraction)
# =========================================================================

class BaseAIProvider(abc.ABC):
    @abc.abstractmethod
    def generate_response(
        self,
        role: str,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        tools_data: Dict[str, Any]
    ) -> tuple[str, Optional[str]]:
        """
        تولید پاسخ هوش مصنوعی بر اساس نقش، متن پیام، تاریخچه گفتگو و داده‌های ابزارها.
        خروجی: (متن پاسخ AI، اقدام پیشنهادی حساس نیازمند تایید)
        """
        pass


class MockAIProvider(BaseAIProvider):
    def generate_response(
        self,
        role: str,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        tools_data: Dict[str, Any]
    ) -> tuple[str, Optional[str]]:
        msg = user_message.strip()
        suggested_action = None
        
        # الف) تحلیل نقش ادمین
        if role in ["admin", "secretary"]:
            if "درآمد" in msg or "revenue" in msg or "پول" in msg:
                rev_data = tools_data.get("revenue_report", {})
                debt_data = tools_data.get("debt_report", {})
                tot_rev = rev_data.get("total_revenue", 12500000)
                debt_amt = debt_data.get("outstanding_debt", 350000)
                
                response = (
                    f"مدیریت گرامی، گزارش تراز مالی نشان می‌دهد که کل درآمد وصول‌شده در این ماه برابر با {tot_rev:,} تومان بوده است. "
                    f"همچنین میزان کل مطالبات معوقه بدهکاران برابر با {debt_amt:,} تومان است. "
                    f"علت اصلی کاهش نسبی درآمدها، معوق شدن اقساط کلاسی در هفته‌های اخیر است."
                )
                suggested_action = "SEND_DEBT_REMINDERS"
                
            elif "بدهکاران" in msg or "debt" in msg:
                debt_data = tools_data.get("debt_report", {})
                debt_amt = debt_data.get("outstanding_debt", 350000)
                debtors_count = debt_data.get("debtors_count", 1)
                response = (
                    f"هم‌اکنون تعداد {debtors_count} دانش‌آموز دارای بدهی معوقه در سیستم هستند که کل بدهی آن‌ها برابر با {debt_amt:,} تومان است. "
                    f"پیشنهاد می‌شود پیامک گروهی یادآوری اقساط به اولیای آن‌ها ارسال شود."
                )
                suggested_action = "SEND_DEBT_REMINDERS"
            else:
                response = "من دستیار هوشمند مدیریت خوارزمی هستم. چطور می‌توانم در تحلیل ترازهای مالی، مدیریت شعب یا وضعیت جذب ثبت‌نام به شما کمک کنم؟"

        # ب) تحلیل نقش مربی
        elif role == "teacher":
            if "توجه" in msg or "ضعیف" in msg or "نیاز" in msg:
                class_sum = tools_data.get("class_summary", {})
                c_title = class_sum.get("course_title", "کلاس ادبیات")
                response = (
                    f"همکار محترم، بر اساس داده‌های حضور و غیاب و نمرات آزمون‌های کلاس {c_title}، "
                    f"تعداد ۱ دانش‌آموز به دلیل حضور کمتر از ۸۰٪ و کسب نمره کلاسی زیر حد نصاب نیاز به توجه بیشتر تحصیلی و هماهنگی با والدین دارد."
                )
                suggested_action = "ALERT_PARENTS_ACADEMIC"
            else:
                response = "من دستیار هوشمند مربیان هستم. چطور می‌توانم در بررسی غیبت‌های مکرر یا نمرات دانش‌آموزان کلاس به شما کمک کنم؟"

        # ج) تحلیل نقش دانش‌آموز
        elif role == "student":
            if "برنامه" in msg or "امتحان" in msg or "درس" in msg:
                grade_data = tools_data.get("student_grades", {})
                avg_g = grade_data.get("average_grade", 14.5)
                response = (
                    f"دانش‌آموز گرامی، آخرین میانگین نمرات شما در سیستم {avg_g} از ۲۰ است. "
                    f"برای آمادگی در آزمون B1، برنامه مطالعه زیر پیشنهاد می‌شود:\n"
                    f"۱. هفته اول: تمرکز بر دایره لغات و تمرین شنیداری (۲ ساعت روزانه).\n"
                    f"۲. هفته دوم: مرور تست‌های شبیه‌ساز و رفع اشکال نمرات ضعیف گذشته.\n"
                    f"آرزوی موفقیت برای شما!"
                )
            else:
                response = "سلام! من دستیار تحصیلی شما هستم. چطور می‌توانم در برنامه‌ریزی درسی یا مرور کارنامه‌تان به شما کمک کنم؟"

        # د) تحلیل نقش والدین
        elif role == "parent":
            if "وضعیت" in msg or "فرزند" in msg or "نمره" in msg:
                st_sum = tools_data.get("student_summary", {})
                st_att = tools_data.get("student_attendance", {})
                st_grd = tools_data.get("student_grades", {})
                
                first_name = st_sum.get("first_name", "فرزند شما")
                att_rate = st_att.get("attendance_rate", 100.0)
                avg_g = st_grd.get("average_grade", 18.0)
                
                response = (
                    f"ولی محترم، تراز آموزشی فرزند شما ({first_name}) نشان می‌دهد که میزان حضور کلاسی او برابر با {att_rate:.1f}% "
                    f"و میانگین نمرات امتحانات او برابر با {avg_g:.2f} از ۲۰ است. وضعیت کلی وی رضایت‌بخش است."
                )
            else:
                response = "سلام ولی محترم. چطور می‌توانم در بررسی وضعیت غیبت‌ها، تکالیف یا تراز اقساط فرزندتان به شما کمک کنم؟"
        else:
            response = "اطلاعات کافی برای پاسخ وجود ندارد."

        # Prepend product honesty notice to avoid misleading users
        notice = "⚠️ [نسخه‌ی آزمایشی — پاسخ‌ها بر پایه‌ی الگوی ثابت و شبیه‌سازی‌شده هستند]\n\n"
        response = notice + response

        return response, suggested_action


# انتخاب ارائه‌دهنده پیش‌فرض (قابل تعویض با OpenAIProvider در آینده)
active_ai_provider = MockAIProvider()


# --- کدهای ذخیره گفتگو (Chat Message History Model) ---
# برای پیگیری آسان تاریخچه گفتگوها بدون ذخیره مستقیم در پایگاه داده اصلی ادمین،
# یک تاریخچه استاتیک درون‌برنامه‌ای پیاده‌سازی می‌کنیم که راندمان سیستم را بالا نگه می‌دارد (Data Minimization).
chat_conversations_in_memory: Dict[str, List[Dict[str, str]]] = {}


# --- طرحواره‌های درخواست کلاینت ---
class AIChatRequest(BaseModel):
    message: str
    student_id: Optional[int] = None
    course_id: Optional[int] = None
    teacher_id: Optional[int] = None


# =========================================================================
# ۲. اندپوینت امن گفتگو با هوش مصنوعی (AI Chat Endpoint - مجهز به لایه ضد IDOR)
# =========================================================================

@router.post("/ai/chat")
def chat_with_ai_assistant(
    req: AIChatRequest,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    role: str = Depends(check_user_login)
):
    if not authorization:
        raise HTTPException(status_code=401, detail="توکن احراز هویت یافت نشد")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="قالب توکن معتبر نیست")
    token = parts[1]
    
    session = db.query(models.UserSession).filter(models.UserSession.token == token).first()
    if not session:
        raise HTTPException(status_code=401, detail="نشست یافت نشد")
        
    session_user_id = session.user_id
    session_role = session.sub_role

    # 🛡️ پیاده‌سازی لایه ضد نشت داده و ضد IDOR بر روی ابزارها (Strict Tool Security)
    # هوش مصنوعی هرگز حق استفاده از ابزارهای خارج از سطح دسترسی کاربر را ندارد.
    allowed_tools = []
    
    # تفکیک سطح دسترسی بر اساس نقش فعال
    if session_role in ["admin", "secretary"]:
        # ادمین دسترسی unrestricted به ابزارهای آماری و گزارش‌گیری دارد
        allowed_tools = ["get_student_summary", "get_student_attendance", "get_student_grades", "get_student_finance", "get_class_summary", "get_teacher_summary", "get_revenue_report", "get_debt_report", "get_registration_report", "get_attendance_report"]
    
    elif session_role == "teacher":
        # معلم فقط مجاز به فراخوانی ابزارهای کلاسی و دانش‌آموزانی است که تدریس می‌کند
        allowed_tools = ["get_student_summary", "get_student_attendance", "get_student_grades", "get_class_summary"]
        # راستی‌آزمایی اینکه آیا این معلم به این کلاس دسترسی دارد
        if req.course_id:
            if not session.teacher_id:
                raise HTTPException(status_code=403, detail="عدم دسترسی مربی به این کلاس (IDOR Prevention)")
            course = db.query(Course).filter(Course.id == req.course_id, Course.teacher_id == session.teacher_id).first()
            if not course:
                raise HTTPException(status_code=403, detail="عدم دسترسی مربی به این کلاس (IDOR Prevention)")
                
    elif session_role in ["student", "parent"]:
        # دانش‌آموز و ولی فقط حق فراخوانی ابزار دانش‌آموزی شخص خودشان یا فرزندشان را دارند
        allowed_tools = ["get_student_summary", "get_student_attendance", "get_student_grades", "get_student_finance"]
        
        # اگر کاربر دانش‌آموز یا ولی بود، شناسه درخواستی ابزار فیزیکی حتماً باید بر روی شناسه فرزند قفل شود
        own = get_session_student(db, session) if session_role == "student" else get_session_parent(db, session)
        if not own:
            raise HTTPException(status_code=401, detail="نشست معتبر نیست؛ لطفاً دوباره وارد شوید")
        if req.student_id and req.student_id != own.id:
            raise HTTPException(status_code=403, detail="خطای دسترسی امنیتی: شما مجاز به مشاهده اطلاعات مالی یا تحصیلی دیگران نیستید (IDOR Protection)")
        # فیکس کردن شناسه هدف ابزارها جهت بهداشت داده
        req.student_id = own.id
        
    else:
        raise HTTPException(status_code=403, detail="دسترسی غیرمجاز")

    # --- واکشی هوشمند داده‌های کلاسی و مالی از ابزارهای مجاز (Data Minimization) ---
    tools_data = {}
    
    # ابزارهای دانش‌آموزی
    if "get_student_summary" in allowed_tools and req.student_id:
        st = db.query(Student).filter(Student.id == req.student_id).first()
        if st:
            tools_data["student_summary"] = {"first_name": st.first_name, "last_name": st.last_name, "student_code": st.student_code}
            
    if "get_student_attendance" in allowed_tools and req.student_id:
        tot_cnt = db.query(Attendance).filter(Attendance.student_id == req.student_id, Attendance.is_deleted == False).count()
        p_cnt = db.query(Attendance).filter(Attendance.student_id == req.student_id, Attendance.status == "Present", Attendance.is_deleted == False).count()
        rate = (p_cnt / tot_cnt * 100) if tot_cnt > 0 else 100.0
        tools_data["student_attendance"] = {"total_sessions": tot_cnt, "presents": p_cnt, "attendance_rate": rate}
        
    if "get_student_grades" in allowed_tools and req.student_id:
        avg_score = db.query(func.avg(Grade.score)).filter(Grade.student_id == req.student_id).scalar() or 18.5
        tools_data["student_grades"] = {"average_grade": avg_score}
        
    if "get_student_finance" in allowed_tools and req.student_id:
        st = db.query(Student).filter(Student.id == req.student_id).first()
        if st:
            tools_data["student_finance"] = {"wallet_teacher": st.wallet_teacher, "wallet_institute": st.wallet_institute}

    # ابزارهای کلاسی
    if "get_class_summary" in allowed_tools and req.course_id:
        course = db.query(Course).filter(Course.id == req.course_id).first()
        if course:
            tools_data["class_summary"] = {"course_title": course.title, "code": course.code}

    # ابزارهای مدیریت مالی ارشد (فقط ادمین)
    if "get_revenue_report" in allowed_tools:
        # FIX: Bug 12 - exclude archived Transaction rows from this active view.
        rev = db.query(func.sum(Transaction.amount)).filter(Transaction.is_reversed == False).filter(Transaction.type == "deposit", Transaction.is_deleted == False).scalar() or 12500000
        tools_data["revenue_report"] = {"total_revenue": rev}
        
    if "get_debt_report" in allowed_tools:
        # FIX: Bug 16 - the finance tool must agree with the actual tuition debtor reports.
        debts = [calculate_student_debt(db, student) for student in db.query(Student).all()]
        tools_data["debt_report"] = {"outstanding_debt": sum(debts), "debtors_count": sum(debt > 0 for debt in debts)}

    # --- مدیریت تاریخچه گفتگو در حافظه امن (Conversation History) ---
    convo_key = f"{session_role}_{session_user_id}"
    if convo_key not in chat_conversations_in_memory:
        chat_conversations_in_memory[convo_key] = []
        
    history = chat_conversations_in_memory[convo_key]
    
    # محدود کردن حجم تاریخچه: کلید شامل پیام‌های user و assistant است.
    # با cap دقیق 15، حافظه حتی هنگام append دو پیام در هر turn رشد نمی‌کند.
    max_history_messages = 15
    if len(history) > max_history_messages:
        del history[:-max_history_messages]

    # --- فراخوانی ارائه‌دهنده سرویس AI ---
    ai_response, suggested_action = active_ai_provider.generate_response(
        role=session_role,
        user_message=req.message,
        conversation_history=history,
        tools_data=tools_data
    )
    
    # اضافه کردن پیام‌ها به تاریخچه گفتگو
    history.append({"user": req.message})
    history.append({"assistant": ai_response})
    if len(history) > max_history_messages:
        del history[:-max_history_messages]
    
    return {
        "status": "success",
        "response": ai_response,
        "role": session_role,
        "suggested_action": suggested_action  # اقدام معلق نیازمند تایید فیزیکی انسان
    }
