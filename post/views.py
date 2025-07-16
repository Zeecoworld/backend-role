from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from .models import Post, Like, Comment, Share
from .serializers import PostSerializer, LikeSerializer, CommentSerializer, ShareSerializer
from django.db.models import Q

class PostListCreateView(generics.ListCreateAPIView):
    queryset = Post.objects.all().order_by('-created_at')
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

class PostRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

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
    def post(self, request, pk):
        post = Post.objects.get(pk=pk)
        Like.objects.get_or_create(user=request.user, post=post)
        return Response({'status': 'liked'})

class ShareView(APIView):
    def post(self, request, pk):
        post = Post.objects.get(pk=pk)
        Share.objects.create(user=request.user, post=post)
        return Response({'status': 'shared'})

class CommentListCreateView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer

    def get_queryset(self):
        return Comment.objects.filter(post_id=self.kwargs['pk'])

    def perform_create(self, serializer):
        post = Post.objects.get(pk=self.kwargs['pk'])
        serializer.save(user=self.request.user, post=post)

class PostSearchView(generics.ListAPIView):
    serializer_class = PostSerializer

    def get_queryset(self):
        query = self.request.GET.get('q', '')
        return Post.objects.filter(Q(content__icontains=query))