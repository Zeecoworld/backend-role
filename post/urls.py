from django.urls import path
from .views import (
    PostListCreateView, 
    PostRetrieveUpdateDestroyView, 
    LikeView, 
    ShareView,
    BookmarkView,
    CommentListCreateView, 
    CommentRepliesView,
    PostSearchView,
    UserPostsView,
    PostStatsView,
    TrendingPostsView,
    MyBookmarksView,
    ContentTypePostsView,
    ImagePostsView,
    VideoPostsView,
    StoryPostsView,
    WorkflowPostsView,
    bulk_delete_posts,
    bulk_update_status
)


urlpatterns = [

        # Content type specific routes (matching React navigation)
    path('type/<str:content_type>/', ContentTypePostsView.as_view(), name='posts-by-type'),
    path('images/', ImagePostsView.as_view(), name='image-posts'),
    path('videos/', VideoPostsView.as_view(), name='video-posts'),
    path('stories/', StoryPostsView.as_view(), name='story-posts'),
    path('workflows/', WorkflowPostsView.as_view(), name='workflow-posts'),

     # Search and discovery
    path('search/', PostSearchView.as_view(), name='post-search'),
    path('trending/', TrendingPostsView.as_view(), name='trending-posts'),

    # Main post routes
    path('', PostListCreateView.as_view(), name='post-list-create'),
    path('<slug:slug>/', PostRetrieveUpdateDestroyView.as_view(), name='post-detail'),
    
    # Post interactions
    path('<int:pk>/like/', LikeView.as_view(), name='like'),
    path('<int:pk>/share/', ShareView.as_view(), name='share'),
    path('<int:pk>/bookmark/', BookmarkView.as_view(), name='bookmark'),
    
    # Comments
    path('<int:pk>/comments/', CommentListCreateView.as_view(), name='comment-list-create'),
    path('comments/<int:comment_id>/replies/', CommentRepliesView.as_view(), name='comment-replies'),
    
   
    

    
    # User specific routes
    path('user/<str:username>/', UserPostsView.as_view(), name='user-posts'),
    path('my-bookmarks/', MyBookmarksView.as_view(), name='my-bookmarks'),
    
    # Analytics and management
    path('<slug:slug>/stats/', PostStatsView.as_view(), name='post-stats'),
    path('bulk/delete/', bulk_delete_posts, name='bulk-delete'),
    path('bulk/update-status/', bulk_update_status, name='bulk-update-status'),
]