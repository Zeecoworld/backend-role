import json
from rest_framework.authtoken.models import Token
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch
from .models import Post, Like, Comment, Share
from .serializers import PostSerializer, CommentSerializer, LikeSerializer, ShareSerializer

User = get_user_model()

class PostSerializerTest(TestCase):
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.post = Post.objects.create(
            author=self.user,
            content='Test post content',
            slug='test-post-slug'
        )
        
    def test_post_serializer_fields(self):
        serializer = PostSerializer(instance=self.post)
        expected_fields = {
            'id', 'slug', 'author', 'content', 'image', 'created_at', 
            'updated_at', 'likes_count', 'comments_count', 'shares_count'
        }
        self.assertEqual(set(serializer.data.keys()), expected_fields)
        
    def test_post_serializer_author_string_representation(self):
        serializer = PostSerializer(instance=self.post)
        self.assertEqual(serializer.data['author'], str(self.user))
        
    def test_post_serializer_counts(self):
        # Create some likes, comments, and shares
        Like.objects.create(user=self.user, post=self.post)
        Comment.objects.create(user=self.user, post=self.post, text='Test comment')
        Share.objects.create(user=self.user, post=self.post)
        
        serializer = PostSerializer(instance=self.post)
        self.assertEqual(serializer.data['likes_count'], 1)
        self.assertEqual(serializer.data['comments_count'], 1)
        self.assertEqual(serializer.data['shares_count'], 1)
        
    def test_post_serializer_slug_readonly(self):
        serializer = PostSerializer()
        self.assertTrue(serializer.fields['slug'].read_only)


class CommentSerializerTest(TestCase):
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.post = Post.objects.create(
            author=self.user,
            content='Test post content'
        )
        self.comment = Comment.objects.create(
            user=self.user,
            post=self.post,
            text='Test comment'
        )
        
    def test_comment_serializer_fields(self):
        serializer = CommentSerializer(instance=self.comment)
        expected_fields = {'id', 'user', 'text', 'created_at'}
        self.assertEqual(set(serializer.data.keys()), expected_fields)
        
    def test_comment_serializer_user_string_representation(self):
        serializer = CommentSerializer(instance=self.comment)
        self.assertEqual(serializer.data['user'], str(self.user))


class LikeSerializerTest(TestCase):
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.post = Post.objects.create(
            author=self.user,
            content='Test post content'
        )
        self.like = Like.objects.create(user=self.user, post=self.post)
        
    def test_like_serializer_fields(self):
        serializer = LikeSerializer(instance=self.like)
        expected_fields = {'id'}
        self.assertEqual(set(serializer.data.keys()), expected_fields)


class ShareSerializerTest(TestCase):
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.post = Post.objects.create(
            author=self.user,
            content='Test post content'
        )
        self.share = Share.objects.create(user=self.user, post=self.post)
        
    def test_share_serializer_fields(self):
        serializer = ShareSerializer(instance=self.share)
        expected_fields = {'id'}
        self.assertEqual(set(serializer.data.keys()), expected_fields)


class PostListCreateViewTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = APIClient()
        self.token = Token.objects.create(user=self.user)
        self.url = reverse('post:post-list-create')

    def test_create_post_authenticated(self):
        """Test creating a post when authenticated"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        data = {
            'title': 'Test Post',
            'content': 'This is a test post content',
            # Remove 'image': None or don't include it at all
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Post.objects.count(), 1)
        post = Post.objects.first()
        self.assertEqual(post.title, 'Test Post')
        self.assertEqual(post.author, self.user)

    def test_posts_ordered_by_created_at(self):
        """Test that posts are ordered by created_at descending"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        
        # Create first post
        post1 = Post.objects.create(
            title='First Post',
            content='First content',
            author=self.user
        )
        
        # Create second post (should be returned first due to ordering)
        post2 = Post.objects.create(
            title='Second Post',
            content='Second content',
            author=self.user
        )
        
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # The most recent post (post2) should be first
        self.assertEqual(response.data['results'][0]['id'], post2.id)


class PostRetrieveUpdateDestroyViewTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        self.client = APIClient()
        self.token = Token.objects.create(user=self.user)
        self.other_token = Token.objects.create(user=self.other_user)
        
        self.post = Post.objects.create(
            title='Test Post',
            content='Test content',
            author=self.user
        )

    def test_update_post_as_non_author(self):
        """Test updating a post as non-author should fail"""
        # Authenticate as different user
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.other_token.key)
        
        url = reverse('post:post-detail', kwargs={'pk': self.post.pk})
        data = {'title': 'Updated Title'}
        response = self.client.patch(url, data)
        
        # Should return 403 Forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

class LikeViewTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = APIClient()
        self.token = Token.objects.create(user=self.user)
        
        self.post = Post.objects.create(
            title='Test Post',
            content='Test content',
            author=self.user
        )

    def test_like_nonexistent_post(self):
        """Test liking a non-existent post"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        
        url = reverse('post:like', kwargs={'pk': 999})  # Non-existent post
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ShareViewTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = APIClient()
        self.token = Token.objects.create(user=self.user)
        
        self.post = Post.objects.create(
            title='Test Post',
            content='Test content',
            author=self.user
        )

    def test_share_nonexistent_post(self):
        """Test sharing a non-existent post"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        
        url = reverse('post:share', kwargs={'pk': 999})  # Non-existent post
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CommentListCreateViewTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = APIClient()
        self.token = Token.objects.create(user=self.user)
        
        self.post = Post.objects.create(
            title='Test Post',
            content='Test content',
            author=self.user
        )

    def test_get_comments_for_post(self):
        """Test getting comments for a post"""
        # Create a comment
        comment = Comment.objects.create(
            text='Test comment',
            user=self.user,
            post=self.post
        )
        
        # Authenticate the client
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        
        url = reverse('post:comment-list-create', kwargs={'pk': self.post.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_create_comment_for_nonexistent_post(self):
        """Test creating a comment for a non-existent post"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        
        url = reverse('post:comment-list-create', kwargs={'pk': 999})  # Non-existent post
        data = {'text': 'Test comment'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class PostSearchViewTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = APIClient()
        self.token = Token.objects.create(user=self.user)
        
        # Create test posts
        self.post1 = Post.objects.create(
            title='Django Tutorial',
            content='Learn Django framework',
            author=self.user
        )
        self.post2 = Post.objects.create(
            title='Python Guide',
            content='Advanced Python programming',
            author=self.user
        )
        
        self.url = reverse('post:post-search')

    def test_search_posts_with_query(self):
        """Test searching posts with a query"""
        # Authenticate the client
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        
        response = self.client.get(self.url, {'q': 'Django'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['title'], 'Django Tutorial')

    def test_search_posts_case_insensitive(self):
        """Test case insensitive search"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        
        response = self.client.get(self.url, {'q': 'django'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_search_posts_partial_match(self):
        """Test partial match search"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        
        response = self.client.get(self.url, {'q': 'Pyth'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_search_posts_no_query(self):
        """Test search without query parameter"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return all posts when no query
        self.assertEqual(len(response.data['results']), 2)

    def test_search_posts_empty_query(self):
        """Test search with empty query"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        
        response = self.client.get(self.url, {'q': ''})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return all posts when empty query
        self.assertEqual(len(response.data['results']), 2)

    def test_search_posts_no_results(self):
        """Test search with no matching results"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        
        response = self.client.get(self.url, {'q': 'nonexistent'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)



class IntegrationTest(APITestCase):
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
    def test_complete_post_workflow(self):
        # Create a post
        post_data = {'content': 'Test post for workflow'}
        post_response = self.client.post(reverse('post-list-create'), post_data)
        self.assertEqual(post_response.status_code, status.HTTP_201_CREATED)
        
        post_id = post_response.data['id']
        
        # Like the post
        like_response = self.client.post(reverse('post:like', kwargs={'pk': post_id}))
        self.assertEqual(like_response.status_code, status.HTTP_200_OK)
        
        # Comment on the post
        comment_data = {'text': 'Great post!'}
        comment_response = self.client.post(
            reverse('post-comments', kwargs={'pk': post_id}), 
            comment_data
        )
        self.assertEqual(comment_response.status_code, status.HTTP_201_CREATED)
        
        # Share the post
        share_response = self.client.post(reverse('post-share', kwargs={'pk': post_id}))
        self.assertEqual(share_response.status_code, status.HTTP_200_OK)
        
        # Get the post and verify counts
        post_detail_response = self.client.get(
            reverse('post-detail', kwargs={'slug': post_response.data['slug']})
        )
        self.assertEqual(post_detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(post_detail_response.data['likes_count'], 1)
        self.assertEqual(post_detail_response.data['comments_count'], 1)
        self.assertEqual(post_detail_response.data['shares_count'], 1)


# Additional test utilities and fixtures
class TestDataMixin:
    
    def create_test_user(self, username='testuser', email='test@example.com'):
        return User.objects.create_user(
            username=username,
            email=email,
            password='testpass123'
        )
        
    def create_test_post(self, author=None, content='Test post content'):
        if author is None:
            author = self.create_test_user()
        return Post.objects.create(author=author, content=content)
        
    def create_test_comment(self, user=None, post=None, text='Test comment'):
        if user is None:
            user = self.create_test_user()
        if post is None:
            post = self.create_test_post(author=user)
        return Comment.objects.create(user=user, post=post, text=text)


# Example of how to run specific tests:
# python manage.py test myapp.tests.PostSerializerTest
# python manage.py test myapp.tests.PostListCreateViewTest.test_create_post_authenticated
# python manage.py test myapp.tests  # Run all tests in this file