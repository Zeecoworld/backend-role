from django.urls import path
from .views import (
    PostListCreateView, PostRetrieveUpdateDestroyView, LikeView, ShareView,
    CommentListCreateView, PostSearchView
)

urlpatterns = [
    path('', PostListCreateView.as_view(), name='post-list-create'),
    path('<slug:slug>/', PostRetrieveUpdateDestroyView.as_view(), name='post-detail'),
    path('<int:pk>/like/', LikeView.as_view(), name='like'),        
    path('<int:pk>/share/', ShareView.as_view(), name='share'),     
    path('<int:pk>/comments/', CommentListCreateView.as_view(), name='comment-list-create'), 
    path('search/', PostSearchView.as_view(), name='post-search'),
]