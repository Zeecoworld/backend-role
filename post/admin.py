from django.contrib import admin
from .models import Post,Like,Share,Comment
# Register your models here.

admin.site.register(Post)
admin.site.register(Share)
admin.site.register(Comment)