from rest_framework import serializers
from .models import Post, Like, Comment, Share, PostMedia, Bookmark
from django.contrib.auth import get_user_model
import json
import filetype
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image as PILImage
import io

User = get_user_model()

def validate_file_type_and_size(file, allowed_types, max_size_mb, field_name):
    if not file:
        return file
    
    # Check file size
    max_size_bytes = max_size_mb * 1024 * 1024
    if file.size > max_size_bytes:
        raise serializers.ValidationError({
            field_name.lower(): f"{field_name} file size cannot exceed {max_size_mb}MB. Current size: {file.size / (1024*1024):.1f}MB"
        })
    
    # Check file type using filetype magic bytes detection
    file_bytes = file.read(261)  # Read first 261 bytes for detection
    file.seek(0)  # Reset file pointer
    
    kind = filetype.guess(file_bytes)
    if not kind:
        raise serializers.ValidationError({
            field_name.lower(): f"Unable to determine {field_name} file type. Please ensure you're uploading a valid file."
        })
    
    if kind.mime not in allowed_types:
        raise serializers.ValidationError({
            field_name.lower(): f"Unsupported {field_name} format. Supported formats: {', '.join([t.split('/')[-1].upper() for t in allowed_types])}"
        })
    
    return file

class PostSerializer(serializers.ModelSerializer):
    """Main post serializer with enhanced validation and AUTO CONTENT TYPE DETECTION"""
    
    author = serializers.SerializerMethodField()
    author_email = serializers.SerializerMethodField()
    likes_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    shares_count = serializers.SerializerMethodField()
    bookmarks_count = serializers.SerializerMethodField()
    slug = serializers.SlugField(read_only=True)
    tags_list = serializers.SerializerMethodField()
    additional_media = serializers.SerializerMethodField()
    workflow_steps_parsed = serializers.SerializerMethodField()
    
    # Enhanced media fields with URLs
    image = serializers.ImageField(required=False, allow_null=True)
    video = serializers.FileField(required=False, allow_null=True)
    image_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    video_thumbnail_url = serializers.SerializerMethodField()
    
    # User interaction fields (read-only)
    is_liked = serializers.SerializerMethodField()
    is_bookmarked = serializers.SerializerMethodField()
    is_owned = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            'id', 'slug', 'author', 'author_email', 'title', 'content', 
            'content_type', 'status', 'image', 'video', 'image_url', 'video_url', 
            'video_thumbnail_url', 'tags', 'tags_list', 'location', 'story_chapters', 
            'workflow_steps', 'workflow_steps_parsed', 'meta_description', 
            'created_at', 'updated_at', 'published_at', 'view_count', 
            'likes_count', 'comments_count', 'shares_count', 'bookmarks_count', 
            'additional_media', 'is_liked', 'is_bookmarked', 'is_owned', 
            'has_media', 'is_video_content', 'is_image_content'
        ]
        read_only_fields = [
            'slug', 'view_count', 'created_at', 'updated_at', 'published_at',
            'image_url', 'video_url', 'video_thumbnail_url'
        ]

    def get_author(self, obj):
        return obj.author.username
    
    def get_author_email(self, obj):
        return obj.author.email

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_comments_count(self, obj):
        return obj.comments.count()

    def get_shares_count(self, obj):
        return obj.shares.count()
    
    def get_bookmarks_count(self, obj):
        return obj.bookmarks.count()
    
    def get_tags_list(self, obj):
        return obj.get_tags_list()
    
    def get_additional_media(self, obj):
        if hasattr(obj, 'additional_media'):
            return PostMediaSerializer(obj.additional_media.all(), many=True).data
        return []
    
    def get_workflow_steps_parsed(self, obj):
        """Parse workflow steps JSON string"""
        if obj.workflow_steps:
            try:
                return json.loads(obj.workflow_steps)
            except json.JSONDecodeError:
                return []
        return []
    
    def get_image_url(self, obj):
        """Get image URL for frontend"""
        return obj.image_url
    
    def get_video_url(self, obj):
        """Get video URL for frontend"""
        return obj.video_url
    
    def get_video_thumbnail_url(self, obj):
        """Get video thumbnail URL for frontend"""
        return obj.video_thumbnail_url
    
    def get_is_liked(self, obj):
        """Check if current user liked this post"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False
    
    def get_is_bookmarked(self, obj):
        """Check if current user bookmarked this post"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.bookmarks.filter(user=request.user).exists()
        return False
    
    def get_is_owned(self, obj):
        """Check if current user owns this post"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.author == request.user
        return False
    
    def validate_content_type(self, value):
        """Validate content type"""
        valid_types = ['post', 'image', 'video', 'story', 'workflow']
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid content type. Must be one of: {valid_types}")
        return value
    
    def validate_image(self, value):
        """Validate image file type and size"""
        if value:
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            validated_file = validate_file_type_and_size(value, allowed_types, 10, 'Image')
            
            # Additional image validation
            try:
                # Open image to verify it's valid
                img = PILImage.open(validated_file)
                img.verify()
                validated_file.seek(0)  # Reset file pointer after verify
                
                # Check dimensions (optional)
                img = PILImage.open(validated_file)
                width, height = img.size
                validated_file.seek(0)
                
                if width < 10 or height < 10:
                    raise serializers.ValidationError({
                        'image': 'Image dimensions too small. Minimum 10x10 pixels.'
                    })
                    
                if width > 8000 or height > 8000:
                    raise serializers.ValidationError({
                        'image': 'Image dimensions too large. Maximum 8000x8000 pixels.'
                    })
                    
            except Exception as e:
                raise serializers.ValidationError({
                    'image': f'Invalid image file: {str(e)}'
                })
                
            return validated_file
        return value
    
    def validate_video(self, value):
        """Validate video file type and size"""
        if value:
            allowed_types = [
                'video/mp4', 'video/webm', 'video/ogg', 
                'video/quicktime', 'video/avi', 'video/mov'
            ]
            validated_file = validate_file_type_and_size(value, allowed_types, 100, 'Video')
            
            # Additional video validation
            if hasattr(validated_file, 'content_type'):
                content_type = validated_file.content_type
            else:
                # Fallback to file extension detection
                file_bytes = validated_file.read(261)
                validated_file.seek(0)
                kind = filetype.guess(file_bytes)
                content_type = kind.mime if kind else 'unknown'
            
            # Check for common video container formats
            valid_containers = ['mp4', 'webm', 'ogg', 'mov', 'avi', 'quicktime']
            if not any(container in content_type.lower() for container in valid_containers):
                raise serializers.ValidationError({
                    'video': f'Unsupported video format: {content_type}. Supported formats: MP4, WebM, OGG, MOV, AVI'
                })
            
            return validated_file
        return value
    
    def validate_workflow_steps(self, value):
        """Validate workflow steps JSON structure"""
        if value:
            try:
                steps = json.loads(value) if isinstance(value, str) else value
                
                # Validate that it's a list
                if not isinstance(steps, list):
                    raise serializers.ValidationError("Workflow steps must be a list")
                
                # Validate each step structure
                for i, step in enumerate(steps):
                    if not isinstance(step, dict):
                        raise serializers.ValidationError(f"Step {i+1} must be an object")
                    
                    # Required fields for each step
                    required_fields = ['title', 'description']
                    for field in required_fields:
                        if field not in step or not step[field]:
                            raise serializers.ValidationError(
                                f"Step {i+1} must have a '{field}' field"
                            )
                    
                    # Optional but validated fields
                    if 'order' in step and not isinstance(step['order'], int):
                        raise serializers.ValidationError(
                            f"Step {i+1} 'order' must be an integer"
                        )
                    
                    if 'duration' in step and not isinstance(step['duration'], (int, str)):
                        raise serializers.ValidationError(
                            f"Step {i+1} 'duration' must be a string or integer"
                        )
                
                return json.dumps(steps) if not isinstance(value, str) else value
                
            except json.JSONDecodeError:
                raise serializers.ValidationError("Workflow steps must be valid JSON")
        
        return value
    
    def validate_tags(self, value):
        """Validate tags format and content"""
        if value:
            # Split tags and validate
            tags = [tag.strip() for tag in value.split(',') if tag.strip()]
            
            # Limit number of tags
            if len(tags) > 10:
                raise serializers.ValidationError("Maximum 10 tags allowed")
            
            # Validate individual tags
            for tag in tags:
                if len(tag) > 50:
                    raise serializers.ValidationError("Each tag must be 50 characters or less")
                
                if not tag.replace(' ', '').replace('-', '').replace('_', '').isalnum():
                    raise serializers.ValidationError(
                        "Tags can only contain letters, numbers, spaces, hyphens, and underscores"
                    )
            
            # Return cleaned tags
            return ', '.join(tags)
        
        return value
    
    def validate_story_chapters(self, value):
        """Validate story chapters"""
        if value is not None:
            if not isinstance(value, int) or value < 1:
                raise serializers.ValidationError("Story chapters must be a positive integer")
            
            if value > 50:
                raise serializers.ValidationError("Maximum 50 chapters allowed")
        
        return value
    
    def validate_content(self, value):
        """Validate content based on length and content"""
        if value:
            # Basic length validation
            if len(value) > 10000:
                raise serializers.ValidationError("Content cannot exceed 10,000 characters")
            
            # Check for minimum content for stories
            content_type = self.initial_data.get('content_type', 'post')
            if content_type == 'story' and len(value.strip()) < 100:
                raise serializers.ValidationError("Story content must be at least 100 characters")
        
        return value
    
    def validate_title(self, value):
        """Validate title"""
        if value and len(value.strip()) > 200:
            raise serializers.ValidationError("Title cannot exceed 200 characters")
        return value.strip() if value else value
    
    def validate_location(self, value):
        """Validate location"""
        if value and len(value) > 200:
            raise serializers.ValidationError("Location cannot exceed 200 characters")
        return value

    def auto_detect_content_type(self, validated_data):
        """
        🔧 AUTO-DETECT CONTENT TYPE - This fixes the image/video mismatch issue
        Priority: User selection > File type detection > Default
        """
        user_content_type = validated_data.get('content_type', 'post')
        image = validated_data.get('image')
        video = validated_data.get('video')
        workflow_steps = validated_data.get('workflow_steps')
        
        print(f"🔧 Content type detection - User selected: {user_content_type}, Has image: {bool(image)}, Has video: {bool(video)}")
        
        # Priority 1: If user explicitly set workflow or story, respect it
        if user_content_type in ['story', 'workflow']:
            print(f"✅ Keeping user-selected content type: {user_content_type}")
            return user_content_type
        
        # Priority 2: Auto-detect based on uploaded files
        if video:
            # If video file is uploaded, it's definitely a video post
            print("✅ Video file detected - setting content_type to 'video'")
            return 'video'
        
        elif image:
            # If only image is uploaded, determine based on context
            if user_content_type == 'image':
                # User explicitly wants image post
                print("✅ Image file + user selected 'image' - setting content_type to 'image'")
                return 'image'
            
            elif user_content_type in ['post', 'video']:
                # User selected post/video but only uploaded image
                # This is likely an image post (fixes the bug!)
                print("✅ Image file + user selected 'post'/'video' - setting content_type to 'image'")
                return 'image'
        
        elif workflow_steps:
            print("✅ Workflow steps detected - setting content_type to 'workflow'")
            return 'workflow'
        
        # Priority 3: Default fallback
        print(f"✅ Using fallback content_type: {user_content_type or 'post'}")
        return user_content_type or 'post'
    
    def validate(self, data):
        """Enhanced cross-field validation with AUTO CONTENT TYPE DETECTION"""
        
        # 🔧 AUTO-DETECT CONTENT TYPE BEFORE VALIDATION
        detected_content_type = self.auto_detect_content_type(data)
        data['content_type'] = detected_content_type
        
        content_type = detected_content_type
        image = data.get('image')
        video = data.get('video')
        title = data.get('title', '')
        content = data.get('content', '')
        workflow_steps = data.get('workflow_steps')
        
        print(f"🔧 Validating with detected content_type: {content_type}")
        
        # Content type specific validation with proper error messages
        if content_type == 'video':
            if not video and not image:
                raise serializers.ValidationError({
                    'video': 'Video posts must include either a video file or a thumbnail image',
                    'image': 'Video posts must include either a video file or a thumbnail image'
                })
        
        elif content_type == 'image':
            if not image:
                raise serializers.ValidationError({
                    'image': 'Image posts must include an image file'
                })
            
            if not title.strip():
                raise serializers.ValidationError({
                    'title': 'Image posts must have a title'
                })
        
        elif content_type == 'story':
            if not title.strip():
                raise serializers.ValidationError({
                    'title': 'Story posts must have a title'
                })
            
            if len(content.strip()) < 100:
                raise serializers.ValidationError({
                    'content': 'Story posts must have at least 100 characters of content'
                })
        
        elif content_type == 'workflow':
            if not workflow_steps:
                raise serializers.ValidationError({
                    'workflow_steps': 'Workflow posts must include workflow steps'
                })
            
            if not title.strip():
                raise serializers.ValidationError({
                    'title': 'Workflow posts must have a title'
                })
        
        elif content_type == 'post':
            # Regular posts validation
            if not title.strip() and not content.strip() and not image and not video:
                raise serializers.ValidationError({
                    'non_field_errors': ['Posts must have either a title, content, or media']
                })
        
        # File size warnings (non-blocking)
        warnings = []
        if video and video.size > 50 * 1024 * 1024:  # 50MB
            warnings.append("Large video files may take longer to upload and process")
        
        if image and image.size > 5 * 1024 * 1024:  # 5MB
            warnings.append("Large image files may take longer to upload")
        
        # Store warnings in context for frontend display
        if warnings and hasattr(self, 'context'):
            self.context['warnings'] = warnings
        
        return data
    
    def create(self, validated_data):
        """Create post with proper content type handling"""
        # Set author to current user
        validated_data['author'] = self.context['request'].user
        
        # Handle workflow steps
        if validated_data.get('workflow_steps'):
            steps = validated_data['workflow_steps']
            if isinstance(steps, (list, dict)):
                validated_data['workflow_steps'] = json.dumps(steps)
        
        # Log final content type for debugging
        print(f"🔧 Creating post with final content_type: {validated_data.get('content_type')}")
        
        return Post.objects.create(**validated_data)

class PostMediaSerializer(serializers.ModelSerializer):
    """Serializer for additional post media"""
    
    media_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    
    class Meta:
        model = PostMedia
        fields = ['id', 'media_file', 'media_url', 'thumbnail_url', 'media_type', 'caption', 'order']
    
    def get_media_url(self, obj):
        if obj.media_file:
            return str(obj.media_file.url)
        return None
    
    def get_thumbnail_url(self, obj):
        if obj.media_file and obj.media_type == 'video':
            # Generate video thumbnail
            import cloudinary
            try:
                return cloudinary.utils.cloudinary_url(
                    obj.media_file.public_id,
                    resource_type='video',
                    format='jpg',
                    transformation=[
                        {'quality': 'auto:good'},
                        {'width': 300, 'height': 200, 'crop': 'fill'}
                    ]
                )[0]
            except:
                return None
        return None

class PostCreateSerializer(PostSerializer):
    """Simplified serializer for post creation with enhanced validation and AUTO DETECTION"""
    
    class Meta(PostSerializer.Meta):
        fields = [
            'title', 'content', 'content_type', 'image', 'video', 
            'tags', 'location', 'story_chapters', 'workflow_steps',
            'meta_description'
        ]

    def to_internal_value(self, data):
        """Enhanced validation with detailed error messages"""
        try:
            return super().to_internal_value(data)
        except serializers.ValidationError as e:
            # Enhance error messages for frontend
            enhanced_errors = {}
            for field, errors in e.detail.items():
                if field == 'image' and 'file size' in str(errors[0]).lower():
                    enhanced_errors[field] = [
                        f"{errors[0]} Please compress your image or choose a smaller file."
                    ]
                elif field == 'video' and 'file size' in str(errors[0]).lower():
                    enhanced_errors[field] = [
                        f"{errors[0]} Please compress your video or choose a smaller file."
                    ]
                else:
                    enhanced_errors[field] = errors
            
            raise serializers.ValidationError(enhanced_errors)

class PostDetailSerializer(PostSerializer):
    """Detailed serializer with comments for single post view"""
    
    recent_comments = serializers.SerializerMethodField()
    
    class Meta(PostSerializer.Meta):
        fields = PostSerializer.Meta.fields + ['recent_comments']
    
    def get_recent_comments(self, obj):
        """Get recent comments for this post"""
        recent_comments = obj.comments.filter(parent=None).order_by('-created_at')[:5]
        return CommentSerializer(recent_comments, many=True).data

class CommentSerializer(serializers.ModelSerializer):
    """Serializer for post comments with reply support"""
    
    user = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()
    replies_count = serializers.SerializerMethodField()
    is_reply = serializers.ReadOnlyField()

    class Meta:
        model = Comment
        fields = [
            'id', 'user', 'user_email', 'text', 'parent', 
            'created_at', 'updated_at', 'is_edited', 'is_reply', 'replies_count'
        ]

    def get_user(self, obj):
        return obj.user.username
    
    def get_user_email(self, obj):
        return obj.user.email
    
    def get_replies_count(self, obj):
        return obj.replies.count()
    
    def validate_text(self, value):
        """Validate comment text"""
        if not value or not value.strip():
            raise serializers.ValidationError("Comment cannot be empty")
        
        if len(value) > 1000:
            raise serializers.ValidationError("Comment cannot exceed 1000 characters")
        
        return value.strip()

class LikeSerializer(serializers.ModelSerializer):
    """Serializer for post likes"""
    
    class Meta:
        model = Like
        fields = ['id', 'created_at']

class ShareSerializer(serializers.ModelSerializer):
    """Serializer for post shares"""
    
    user = serializers.SerializerMethodField()
    
    class Meta:
        model = Share
        fields = ['id', 'user', 'share_text', 'created_at']
    
    def get_user(self, obj):
        return obj.user.username
    
    def validate_share_text(self, value):
        """Validate share text"""
        if value and len(value) > 280:
            raise serializers.ValidationError("Share text cannot exceed 280 characters")
        return value

class BookmarkSerializer(serializers.ModelSerializer):
    """Serializer for post bookmarks"""
    
    class Meta:
        model = Bookmark
        fields = ['id', 'created_at']

class PostStatsSerializer(serializers.ModelSerializer):
    """Serializer for post statistics and analytics"""
    
    engagement_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = Post
        fields = [
            'id', 'title', 'content_type', 'view_count', 
            'likes_count', 'comments_count', 'shares_count',
            'created_at', 'engagement_rate'
        ]
    
    def get_engagement_rate(self, obj):
        """Calculate engagement rate"""
        if obj.view_count > 0:
            total_engagement = obj.likes.count() + obj.comments.count() + obj.shares.count()
            return round((total_engagement / obj.view_count) * 100, 2)
        return 0

# Specialized serializers for different content types
class VideoPostSerializer(PostSerializer):
    """Serializer specifically for video content with additional video metadata"""
    
    video_duration = serializers.SerializerMethodField()
    video_format = serializers.SerializerMethodField()
    
    class Meta(PostSerializer.Meta):
        fields = PostSerializer.Meta.fields + ['video_duration', 'video_format']
    
    def get_video_duration(self, obj):
        """Get video duration if available"""
        # This would require additional processing or metadata storage
        return None
    
    def get_video_format(self, obj):
        """Get video format"""
        if obj.video:
            # Extract format from cloudinary metadata
            try:
                return obj.video.format or 'mp4'
            except:
                return 'mp4'
        return None

# Content type specific serializers
class StoryPostSerializer(PostSerializer):
    """Serializer specifically for story content"""
    
    class Meta(PostSerializer.Meta):
        fields = PostSerializer.Meta.fields
    
    def validate(self, data):
        data = super().validate(data)
        if data.get('content_type') == 'story':
            if not data.get('title'):
                raise serializers.ValidationError("Story posts must have a title")
            if len(data.get('content', '')) < 100:
                raise serializers.ValidationError("Story content should be at least 100 characters")
        return data

class WorkflowPostSerializer(PostSerializer):
    """Serializer specifically for workflow content"""
    
    class Meta(PostSerializer.Meta):
        fields = PostSerializer.Meta.fields
    
    def validate(self, data):
        data = super().validate(data)
        if data.get('content_type') == 'workflow':
            if not data.get('workflow_steps'):
                raise serializers.ValidationError("Workflow posts must have steps defined")
        return data

class ImagePostSerializer(PostSerializer):
    """Serializer specifically for image content"""
    
    class Meta(PostSerializer.Meta):
        fields = PostSerializer.Meta.fields
    
    def validate(self, data):
        data = super().validate(data)
        if data.get('content_type') == 'image':
            if not data.get('image'):
                raise serializers.ValidationError("Image posts must include an image")
        return data