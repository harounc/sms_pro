from django.contrib import admin
from .models import Campaign, Message, Sender

admin.site.register(Campaign)
admin.site.register(Message)
admin.site.register(Sender)