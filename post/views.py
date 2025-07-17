from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from .models import Post, Like, Comment, Share
from django.shortcuts import get_object_or_404
from .serializers import PostSerializer, LikeSerializer, CommentSerializer, ShareSerializer
from django.db.models import Q

class PostListCreateView(generics.ListCreateAPIView):
    queryset = Post.objects.all().order_by('-created_at')
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        # Save with the authenticated user as author
        serializer.save(author=self.request.user)
        
    def create(self, request, *args, **kwargs):
        
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PostRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'slug'  
    lookup_url_kwarg = 'slug'

    def get_object(self):
        obj = super().get_object()
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            if obj.author != self.request.user:
                raise PermissionDenied("You can only edit your own posts")
        return obj
    
    def get_queryset(self):
        return Post.objects.select_related('author').prefetch_related('likes', 'comments', 'shares')
    
class LikeView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        Like.objects.get_or_create(user=request.user, post=post)
        return Response({'status': 'liked'})

class ShareView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        Share.objects.create(user=request.user, post=post)
        return Response({'status': 'shared'})

class CommentListCreateView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Comment.objects.filter(post_id=self.kwargs['pk']).order_by('-created_at')

    def perform_create(self, serializer):
        post = get_object_or_404(Post, pk=self.kwargs['pk'])
        serializer.save(user=self.request.user, post=post)

class PostSearchView(generics.ListAPIView):
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        query = self.request.GET.get('q', '')
        if query:
            return Post.objects.filter(
                Q(content__icontains=query) | Q(title__icontains=query)
            ).order_by('-created_at')
        return Post.objects.all().order_by('-created_at')
