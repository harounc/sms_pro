from django.contrib import admin
from .models import Contact, Campaign, Message

admin.site.register(Contact)
admin.site.register(Campaign)
admin.site.register(Message)