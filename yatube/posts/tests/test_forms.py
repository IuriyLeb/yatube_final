from http import HTTPStatus
from datetime import datetime as dt

import shutil
import tempfile
from django.conf import settings

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile


from posts.models import Post, User, Group
from posts.tests.test_views import create_redirect_url

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostFormTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='brother')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test_group')

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(PostFormTest.user)

    def test_create_post_from_form(self):
        """Пост создается со значениями, заданными в форме."""
        posts_count = Post.objects.count()
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        uploaded = SimpleUploadedFile(
            name='small.gif',
            content=small_gif,
            content_type='image/gif'
        )
        form_data = {
            'text': 'Тестовый текст',
            'group': PostFormTest.group.id,
            'image': uploaded,
            'author': PostFormTest.user
        }

        response = self.authorized_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertRedirects(
            response,
            reverse(
                'posts:profile',
                kwargs={'username': PostFormTest.user}))
        self.assertEqual(Post.objects.count(), posts_count + 1)

        pk = Post.objects.first().pk
        created_post = Post.objects.get(pk=pk)
        self.assertTrue(
            created_post.image,
            form_data['image']
        )
        self.assertEqual(
            created_post.text,
            form_data['text']
        )

        self.assertEqual(
            created_post.author,
            PostFormTest.user
        )

    def test_edit_post_from_form(self):
        """Запись в БД изменяется при изменении поста."""
        posts_count = Post.objects.count()
        form_data = {
            'text': 'Тестовый текст',
        }
        self.authorized_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True
        )
        form_data = {
            'text': 'Новый тестовый текст',
        }
        self.assertEqual(Post.objects.count(), posts_count + 1)
        pk = Post.objects.first().pk
        response = self.authorized_client.post(
            reverse('posts:post_edit', kwargs={'post_id': pk}),
            data=form_data,
            follow=True
        )
        self.assertEqual(
            Post.objects.get(pk=pk).text,
            form_data['text']
        )
        self.assertRedirects(
            response,
            reverse('posts:post_detail', kwargs={'post_id': pk}))

    def test_non_login_user_redirects(self):
        """Неавторизованного пользователя
        перенаправляет на страницу авторизации."""
        posts_count = Post.objects.count()
        form_data = {
            'text': 'Тестовый текст',
        }
        response = self.guest_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(Post.objects.count(), posts_count)
        self.assertRedirects(response, create_redirect_url(
            'users:login',
            'posts:post_create'))


class CommentTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='Test_user')
        cls.post = Post.objects.create(
            text='Тестовый текст',
            pub_date=dt.now(),
            author=CommentTest.user,)
        cls.form_data = {'text': 'Test_comment_text'}

    def setUp(self):
        self.unauthorized_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(CommentTest.user)

    def test_create_comment_unauthorized(self):
        """При попытке оставить комментарий
        неавторизованный пользователь перенаправляется
         на страницу логина."""
        response = self.unauthorized_client.post(
            reverse(
                'posts:add_comment',
                kwargs={'post_id': CommentTest.post.id}),
            data=CommentTest.form_data,
            follow=True)
        self.assertRedirects(response, create_redirect_url(
            'users:login',
            'posts:add_comment',
            {'post_id': CommentTest.post.id}))

    def test_create_comment(self):
        """Комментарий может создать только авторизованный пользователь."""
        self.authorized_client.post(
            reverse(
                'posts:add_comment',
                kwargs={'post_id': CommentTest.post.id}),
            data=CommentTest.form_data,
            follow=True
        )
        comment = CommentTest.post.comments.get()
        self.assertEqual(comment.text, CommentTest.form_data['text'])
