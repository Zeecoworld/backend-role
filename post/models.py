import uuid
from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from cloudinary.models import CloudinaryField
from django.utils.text import slugify
from django.urls import reverse
import cloudinary

User = get_user_model()


class Post(models.Model):
    CONTENT_TYPE_CHOICES = [
        ('post', 'Post'),
        ('image', 'Image'),
        ('video', 'Video'),
        ('story', 'Story'),
        ('workflow', 'Workflow'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    content = models.TextField()
    content_type = models.CharField(
        max_length=20,
        choices=CONTENT_TYPE_CHOICES,
        default='post',
        help_text="Type of content being posted"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='published'
    )

    # Media fields
    image = CloudinaryField('posts', null=True, blank=True)
    video = CloudinaryField('videos', null=True, blank=True, resource_type='video')

    # Additional fields
    tags = models.CharField(
        max_length=500,
        blank=True,
        help_text="Comma-separated tags"
    )
    location = models.CharField(max_length=200, blank=True)

    # Story-specific
    story_chapters = models.PositiveIntegerField(
        default=1,
        help_text="Number of chapters for story content"
    )

    # Workflow-specific
    workflow_steps = models.TextField(
        blank=True,
        help_text="JSON string of workflow steps"
    )

    # SEO and metadata
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    # Engagement
    view_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['content_type', '-created_at']),
            models.Index(fields=['author', '-created_at']),
            models.Index(fields=['status', '-published_at']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.generate_unique_slug()
        
        # Auto-set published_at when status changes to published
        if self.status == 'published' and not self.published_at:
            from django.utils import timezone
            self.published_at = timezone.now()
            
        super().save(*args, **kwargs)
    
    def generate_unique_slug(self):
        if hasattr(self, 'title') and self.title:
            base_slug = slugify(self.title)
        else:
            base_slug = slugify(self.content[:50])  
        
        slug = base_slug
        counter = 1
        while Post.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        return slug
    
    def get_absolute_url(self):
        return reverse('post-detail', kwargs={'slug': self.slug})
    
    def get_tags_list(self):
        """Return tags as a list"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
        return []
    
    def increment_view_count(self):
        """Safely increment view count"""
        Post.objects.filter(pk=self.pk).update(view_count=models.F('view_count') + 1)
    
    @property
    def is_video_content(self):
        return self.content_type == 'video' or bool(self.video)
    
    @property
    def is_image_content(self):
        return self.content_type == 'image' or bool(self.image)
    
    @property
    def has_media(self):
        return bool(self.image or self.video)
    
    @property
    def video_url(self):
        """Get video URL for frontend consumption"""
        if self.video:
            return str(self.video.url)
        return None
    
    @property
    def video_thumbnail_url(self):
        """Get video thumbnail URL"""
        if self.video:
            # Cloudinary can generate video thumbnails
            video_public_id = self.video.public_id
            return cloudinary.utils.cloudinary_url(
                video_public_id,
                resource_type='video',
                format='jpg',
                transformation=[
                    {'quality': 'auto:good'},
                    {'width': 500, 'height': 300, 'crop': 'fill'}
                ]
            )[0]
        return None
    
    @property 
    def image_url(self):
        """Get image URL for frontend consumption"""
        if self.image:
            return str(self.image.url)
        return None
    
    def __str__(self):
        return f"{self.get_content_type_display()}: {self.title}"

class PostMedia(models.Model):
    """Additional media files for posts that support multiple media"""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='additional_media')
    media_file = CloudinaryField('post_media', resource_type='auto')
    media_type = models.CharField(
        max_length=20,
        choices=[
            ('image', 'Image'),
            ('video', 'Video'),
            ('audio', 'Audio'),
            ('document', 'Document'),
        ]
    )
    caption = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order', 'created_at']
    
    def __str__(self):
        return f"{self.post.title} - {self.media_type} {self.order}"

class Like(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'post')
        indexes = [
            models.Index(fields=['post', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} likes {self.post.title}"

class Comment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    text = models.TextField(max_length=1000)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_edited = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['post', '-created_at']),
            models.Index(fields=['parent', '-created_at']),
        ]
    
    def save(self, *args, **kwargs):
        if self.pk:  # If updating existing comment
            self.is_edited = True
        super().save(*args, **kwargs)
    
    @property
    def is_reply(self):
        return self.parent is not None
    
    def __str__(self):
        return f"{self.user.username} on {self.post.title}: {self.text[:50]}..."

class Share(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='shares')
    share_text = models.CharField(max_length=280, blank=True, help_text="Optional text when sharing")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'post')
        indexes = [
            models.Index(fields=['post', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} shared {self.post.title}"

class PostView(models.Model):
    """Track post views for analytics"""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='post_views')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        help_text="Null for anonymous views"
    )
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['post', '-created_at']),
            models.Index(fields=['ip_address', '-created_at']),
        ]

class Bookmark(models.Model):
    """User bookmarks for posts"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='bookmarks')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'post')
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} bookmarked {self.post.title}"