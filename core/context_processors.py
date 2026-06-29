from django.utils import timezone

from messaging.models import Message

'''
def sidebar_sms_counter(request):

    user = getattr(request, "user", None)

    if not user or not getattr(user, "is_authenticated", False):
        return {"sidebar_sms_today": 0}

    if getattr(user, "role", None) == "admin":
        return {"sidebar_sms_today": 0}

    company = getattr(user, "company", None)
    if not company:
        return {"sidebar_sms_today": 0}

    today = timezone.now().date()

    sms_today = Message.objects.for_company(company).filter(
        status="sent",
        sent_at__date=today,
    ).count()

    return {"sidebar_sms_today": sms_today}
'''

def sidebar_sms_counter(request):

    if not request.user.is_authenticated:
        return {}

    company = getattr(request.user, "company", None)

    if not company:
        return {}

    from messaging.models import Message
    from django.utils import timezone

    today = timezone.now().date()

    sms_today = Message.objects.filter(
        company=company,
        created_at__date=today
    ).count()

    return {
        "sidebar_sms_today": sms_today
    }