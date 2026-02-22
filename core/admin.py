from django.contrib import admin
from .models import Transaction, ApiLog

admin.site.register(Transaction)
admin.site.register(ApiLog)