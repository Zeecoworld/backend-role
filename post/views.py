from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from django.http import Http404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend
from .models import Post, Like, Comment, Share, Bookmark, PostView
from django.shortcuts import get_object_or_404
from .serializers import (
    PostSerializer, PostCreateSerializer, PostDetailSerializer,
    LikeSerializer, CommentSerializer, ShareSerializer, 
    BookmarkSerializer, PostStatsSerializer,
    StoryPostSerializer, WorkflowPostSerializer
)
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
import json

class PostListCreateView(generics.ListCreateAPIView):
    """List all posts or create a new post"""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['content_type', 'author', 'status']
    search_fields = ['title', 'content', 'tags']
    ordering_fields = ['created_at', 'view_count', 'likes_count']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = Post.objects.select_related('author').prefetch_related(
            'likes', 'comments', 'shares', 'bookmarks', 'additional_media'
        ).filter(status='published')
        
        # Filter by content type if specified
        content_type = self.request.query_params.get('content_type')
        if content_type:
            queryset = queryset.filter(content_type=content_type)
        
        return queryset

    def get_serializer_class(self):
        if self.request.method == 'POST':
            # Use different serializers based on content type
            content_type = self.request.data.get('content_type', 'post')
            if content_type == 'story':
                return StoryPostSerializer
            elif content_type == 'workflow':
                return WorkflowPostSerializer
            return PostCreateSerializer
        return PostSerializer

    def perform_create(self, serializer):
        """Save with the authenticated user as author"""
        serializer.save(author=self.request.user)
        
    def create(self, request, *args, **kwargs):
        """Enhanced create with content type validation"""
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                post = serializer.save()
                
                # Return detailed post data
                response_serializer = PostDetailSerializer(
                    post, 
                    context={'request': request}
                )
                
                return Response(
                    response_serializer.data, 
                    status=status.HTTP_201_CREATED
                )
            else:
                return Response(
                    serializer.errors, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {'error': f'Failed to create post: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class PostRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'slug'
    
    def get_queryset(self):
        return Post.objects.all()
    
    def get_object(self):
        slug = self.kwargs.get('slug')
        
        try:
            obj = Post.objects.get(slug=slug)
            return obj
        except Post.DoesNotExist:
            posts = Post.objects.all().values_list('slug', 'title')
            raise Http404("Post not found")
    
    def get_client_ip(self):
        """Get client IP address"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip

class ContentTypePostsView(generics.ListAPIView):
    """Get posts by content type"""
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering = ['-created_at']

    def get_queryset(self):
        content_type = self.kwargs.get('content_type')
        return Post.objects.filter(
            content_type=content_type,
            status='published'
        ).select_related('author').prefetch_related(
            'likes', 'comments', 'shares', 'bookmarks'
        )

class LikeView(APIView):
    """Like or unlike a post"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        like, created = Like.objects.get_or_create(user=request.user, post=post)
        
        if not created:
            # Unlike if already liked
            like.delete()
            return Response({
                'status': 'unliked',
                'likes_count': post.likes.count()
            })
        
        return Response({
            'status': 'liked',
            'likes_count': post.likes.count()
        })

class ShareView(APIView):
    """Share a post"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        share_text = request.data.get('share_text', '')
        
        share, created = Share.objects.get_or_create(
            user=request.user, 
            post=post,
            defaults={'share_text': share_text}
        )
        
        if not created:
            # Update share text if already shared
            share.share_text = share_text
            share.save()
        
        return Response({
            'status': 'shared',
            'shares_count': post.shares.count(),
            'share_id': share.id
        })

class BookmarkView(APIView):
    """Bookmark or unbookmark a post"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        bookmark, created = Bookmark.objects.get_or_create(
            user=request.user, 
            post=post
        )
        
        if not created:
            # Remove bookmark if already bookmarked
            bookmark.delete()
            return Response({
                'status': 'unbookmarked',
                'bookmarks_count': post.bookmarks.count()
            })
        
        return Response({
            'status': 'bookmarked',
            'bookmarks_count': post.bookmarks.count()
        })

class CommentListCreateView(generics.ListCreateAPIView):
    """List comments for a post or create a new comment"""
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering = ['-created_at']

    def get_queryset(self):
        post_id = self.kwargs['pk']
        return Comment.objects.filter(
            post_id=post_id,
            parent=None  # Only top-level comments
        ).select_related('user').prefetch_related('replies')

    def perform_create(self, serializer):
        post = get_object_or_404(Post, pk=self.kwargs['pk'])
        parent_id = self.request.data.get('parent')
        parent = None
        
        if parent_id:
            parent = get_object_or_404(Comment, pk=parent_id, post=post)
        
        serializer.save(user=self.request.user, post=post, parent=parent)

class CommentRepliesView(generics.ListAPIView):
    """Get replies for a specific comment"""
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        comment_id = self.kwargs['comment_id']
        return Comment.objects.filter(
            parent_id=comment_id
        ).select_related('user').order_by('created_at')

class PostSearchView(generics.ListAPIView):
    """Search posts with advanced filtering"""
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'content', 'tags']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = Post.objects.filter(status='published').select_related('author')
        
        query = self.request.GET.get('q', '')
        content_type = self.request.GET.get('content_type', '')
        author = self.request.GET.get('author', '')
        tags = self.request.GET.get('tags', '')
        
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | 
                Q(content__icontains=query) |
                Q(tags__icontains=query)
            )
        
        if content_type:
            queryset = queryset.filter(content_type=content_type)
        
        if author:
            queryset = queryset.filter(author__username__icontains=author)
        
        if tags:
            tag_list = [tag.strip() for tag in tags.split(',')]
            for tag in tag_list:
                queryset = queryset.filter(tags__icontains=tag)
        
        return queryset.distinct()

class UserPostsView(generics.ListAPIView):
    """Get posts by a specific user"""
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['content_type']
    ordering = ['-created_at']

    def get_queryset(self):
        username = self.kwargs['username']
        queryset = Post.objects.filter(
            author__username=username,
            status='published'
        ).select_related('author').prefetch_related('likes', 'comments', 'shares')
        
        # If viewing own posts, include drafts
        if self.request.user.username == username:
            queryset = Post.objects.filter(author__username=username)
        
        return queryset

class PostStatsView(generics.RetrieveAPIView):
    """Get detailed statistics for a post"""
    serializer_class = PostStatsSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'slug'

    def get_queryset(self):
        return Post.objects.annotate(
            likes_count=Count('likes'),
            comments_count=Count('comments'),
            shares_count=Count('shares')
        )

    def get_object(self):
        obj = super().get_object()
        # Only post owner can view detailed stats
        if obj.author != self.request.user:
            raise PermissionDenied("You can only view stats for your own posts")
        return obj

class TrendingPostsView(generics.ListAPIView):
    """Get trending posts based on engagement"""
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Get posts from last 7 days with high engagement
        from datetime import timedelta
        week_ago = timezone.now() - timedelta(days=7)
        
        return Post.objects.filter(
            created_at__gte=week_ago,
            status='published'
        ).annotate(
            engagement_score=Count('likes') + Count('comments') + Count('shares')
        ).order_by('-engagement_score', '-view_count')[:20]

class MyBookmarksView(generics.ListAPIView):
    """Get current user's bookmarked posts"""
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]
    ordering = ['-created_at']

    def get_queryset(self):
        bookmarked_post_ids = Bookmark.objects.filter(
            user=self.request.user
        ).values_list('post_id', flat=True)
        
        return Post.objects.filter(
            id__in=bookmarked_post_ids,
            status='published'
        ).select_related('author').prefetch_related('likes', 'comments', 'shares')

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def bulk_delete_posts(request):
    """Bulk delete posts (owner only)"""
    post_ids = request.data.get('post_ids', [])
    
    if not post_ids:
        return Response(
            {'error': 'No post IDs provided'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Only allow deletion of own posts
    posts = Post.objects.filter(
        id__in=post_ids,
        author=request.user
    )
    
    deleted_count = posts.count()
    posts.delete()
    
    return Response({
        'message': f'Successfully deleted {deleted_count} posts',
        'deleted_count': deleted_count
    })

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def bulk_update_status(request):
    """Bulk update post status (owner only)"""
    post_ids = request.data.get('post_ids', [])
    new_status = request.data.get('status', 'published')
    
    if not post_ids:
        return Response(
            {'error': 'No post IDs provided'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if new_status not in ['draft', 'published', 'archived']:
        return Response(
            {'error': 'Invalid status'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Only allow updating own posts
    posts = Post.objects.filter(
        id__in=post_ids,
        author=request.user
    )
    
    updated_count = posts.update(status=new_status)
    
    return Response({
        'message': f'Successfully updated {updated_count} posts to {new_status}',
        'updated_count': updated_count
    })

# Content-type specific views
class ImagePostsView(ContentTypePostsView):
    """Get all image posts"""
    def get_queryset(self):
        return super().get_queryset().filter(content_type='image')

class VideoPostsView(ContentTypePostsView):
    """Get all video posts"""
    def get_queryset(self):
        return super().get_queryset().filter(content_type='video')

class StoryPostsView(ContentTypePostsView):
    """Get all story posts"""
    def get_queryset(self):
        return super().get_queryset().filter(content_type='story')

class WorkflowPostsView(ContentTypePostsView):
    """Get all workflow posts"""
    def get_queryset(self):
        return super().get_queryset().filter(content_type='workflow')