from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from django import forms
from .models import Post, Like, Share, Comment, PostMedia, Bookmark, PostView

class PostAdminForm(forms.ModelForm):
    """Custom form to ensure slug field is included"""
    
    class Meta:
        model = Post
        fields = '__all__'  
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make slug field optional but visible
        self.fields['slug'].required = False
        self.fields['slug'].help_text = 'Leave blank to auto-generate from title'

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    form = PostAdminForm  # Use custom form
    
    list_display = [
        'title', 'author', 'content_type', 'status', 'view_count',
        'likes_count', 'comments_count', 'created_at', 'published_at'
    ]
    list_filter = [
        'content_type', 'status', 'created_at', 'published_at'
    ]
    search_fields = ['title', 'content', 'author__username', 'tags']
    
    # NOW this should work since slug is in the form
    prepopulated_fields = {'slug': ('title',)}
    
    readonly_fields = [
        'view_count', 'created_at', 'updated_at', 
        'likes_count', 'comments_count', 'shares_count'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'author', 'content_type', 'status')
        }),
        ('Content', {
            'fields': ('content', 'meta_description')
        }),
        ('Media', {
            'fields': ('image', 'video'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('tags', 'location'),
            'classes': ('collapse',)
        }),
        ('Content Type Specific', {
            'fields': ('story_chapters', 'workflow_steps'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('view_count', 'likes_count', 'comments_count', 'shares_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'published_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['make_published', 'make_draft', 'make_archived']
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(
            likes_count=Count('likes'),
            comments_count=Count('comments'),
            shares_count=Count('shares')
        )
    
    def save_model(self, request, obj, form, change):
        """Custom save to handle slug generation"""
        if not obj.slug and obj.title:
            # Generate slug if empty
            obj.slug = obj.generate_unique_slug()
        super().save_model(request, obj, form, change)
    
    def likes_count(self, obj):
        return obj.likes_count
    likes_count.short_description = 'Likes'
    likes_count.admin_order_field = 'likes_count'
    
    def comments_count(self, obj):
        return obj.comments_count
    comments_count.short_description = 'Comments'
    comments_count.admin_order_field = 'comments_count'
    
    def shares_count(self, obj):
        return obj.shares_count
    shares_count.short_description = 'Shares'
    shares_count.admin_order_field = 'shares_count'
    
    def make_published(self, request, queryset):
        queryset.update(status='published')
    make_published.short_description = "Mark selected posts as published"
    
    def make_draft(self, request, queryset):
        queryset.update(status='draft')
    make_draft.short_description = "Mark selected posts as draft"
    
    def make_archived(self, request, queryset):
        queryset.update(status='archived')
    make_archived.short_description = "Mark selected posts as archived"

class PostMediaInline(admin.TabularInline):
    model = PostMedia
    extra = 1
    fields = ['media_file', 'media_type', 'caption', 'order']

@admin.register(PostMedia)
class PostMediaAdmin(admin.ModelAdmin):
    list_display = ['post', 'media_type', 'caption', 'order', 'created_at']
    list_filter = ['media_type', 'created_at']
    search_fields = ['post__title', 'caption']

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = [
        'post_title', 'user', 'text_preview', 'parent', 
        'is_edited', 'created_at'
    ]
    list_filter = ['is_edited', 'created_at']
    search_fields = ['text', 'user__username', 'post__title']
    readonly_fields = ['created_at', 'updated_at']
    
    def post_title(self, obj):
        return obj.post.title
    post_title.short_description = 'Post'
    
    def text_preview(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    text_preview.short_description = 'Comment'

@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ['user', 'post_title', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'post__title']
    
    def post_title(self, obj):
        return obj.post.title
    post_title.short_description = 'Post'

@admin.register(Share)
class ShareAdmin(admin.ModelAdmin):
    list_display = ['user', 'post_title', 'share_text_preview', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'post__title', 'share_text']
    
    def post_title(self, obj):
        return obj.post.title
    post_title.short_description = 'Post'
    
    def share_text_preview(self, obj):
        if obj.share_text:
            return obj.share_text[:30] + '...' if len(obj.share_text) > 30 else obj.share_text
        return '-'
    share_text_preview.short_description = 'Share Text'

@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ['user', 'post_title', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'post__title']
    
    def post_title(self, obj):
        return obj.post.title
    post_title.short_description = 'Post'

@admin.register(PostView)
class PostViewAdmin(admin.ModelAdmin):
    list_display = [
        'post_title', 'user', 'ip_address', 'user_agent_preview', 'created_at'
    ]
    list_filter = ['created_at']
    search_fields = ['post__title', 'user__username', 'ip_address']
    readonly_fields = ['created_at']
    
    def post_title(self, obj):
        return obj.post.title
    post_title.short_description = 'Post'
    
    def user_agent_preview(self, obj):
        if obj.user_agent:
            return obj.user_agent[:50] + '...' if len(obj.user_agent) > 50 else obj.user_agent
        return '-'
    user_agent_preview.short_description = 'User Agent'


admin.site.site_header = "5th Social Admin"
admin.site.site_title = "5th Social"
admin.site.index_title = "Welcome to 5th Social Administration"