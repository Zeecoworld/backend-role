from rest_framework import serializers
from .models import Post, Like, Comment, Share

class CommentSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField() 

    class Meta:
        model = Comment
        fields = ['id', 'user', 'user_email', 'text', 'created_at']

    def get_user(self, obj):
        return obj.user.username
    
    def get_user_email(self, obj):
        return obj.user.email

class PostSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    author_email = serializers.SerializerMethodField()  
    likes_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    shares_count = serializers.SerializerMethodField()
    slug = serializers.SlugField(read_only=True)
    image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Post
        fields = [
            'id', 'slug', 'author', 'author_email', 'title', 'content', 'image', 
            'created_at', 'updated_at', 'likes_count', 'comments_count', 'shares_count'
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
    
    def create(self, validated_data):
        
        post = Post.objects.create(**validated_data)
        
        return post


class LikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Like
        fields = ['id']

class ShareSerializer(serializers.ModelSerializer):
    class Meta:
        model = Share
        fields = ['id']