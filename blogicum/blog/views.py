from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, UpdateView
from django.urls import reverse

from .forms import CommentForm, PostForm, UserEditForm
from .models import Category, Comment, Post

User = get_user_model()
POSTS_PER_PAGE = 10


def filter_published_posts(queryset):
    """Фильтрация записей по опубликованности."""
    return queryset.filter(
        is_published=True,
        category__is_published=True,
        pub_date__lte=timezone.now()
    )


def annotate_comment_count(queryset):
    """Вычисление количества комментариев к постам."""
    return queryset.annotate(comment_count=Count('comments'))


def paginate_queryset(queryset, request):
    """Вычисление одной страницы пагинатора."""
    paginator = Paginator(queryset, POSTS_PER_PAGE)
    page_number = request.GET.get('page')
    return paginator.get_page(page_number)


def get_published_posts():
    """Базовый queryset опубликованных постов с нужными связями."""
    queryset = Post.objects.select_related('category', 'location', 'author')
    queryset = filter_published_posts(queryset)
    queryset = annotate_comment_count(queryset)
    return queryset.order_by('-pub_date')


# -------- Views --------

def index(request):
    """Главная страница / Лента записей."""
    page_obj = paginate_queryset(get_published_posts(), request)
    return render(request, 'blog/index.html', {'page_obj': page_obj})


def post_detail(request, post_id):
    """Отображение полного описания публикации."""
    post = get_object_or_404(Post, pk=post_id)
    if request.user != post.author:
        post = get_object_or_404(
            filter_published_posts(Post.objects.select_related(
                'category', 'location', 'author'
            )),
            pk=post_id
        )
    comments = post.comments.select_related('author')
    form = CommentForm()
    return render(request, 'blog/detail.html', {
        'post': post,
        'comments': comments,
        'form': form
    })


def category_posts(request, category_slug):
    """Отображение публикаций категории."""
    category = get_object_or_404(
        Category,
        slug=category_slug,
        is_published=True
    )
    page_obj = paginate_queryset(
        get_published_posts().filter(category=category),
        request
    )
    return render(request, 'blog/category.html', {
        'category': category,
        'page_obj': page_obj
    })


def profile(request, username):
    """Страница пользователя."""
    profile_user = get_object_or_404(User, username=username)
    # Автор видит все свои посты включая неопубликованные и отложенные
    if request.user == profile_user:
        post_list = annotate_comment_count(
            Post.objects.select_related('category', 'location', 'author')
            .filter(author=profile_user)
        ).order_by('-pub_date')
    else:
        post_list = get_published_posts().filter(author=profile_user)
    page_obj = paginate_queryset(post_list, request)
    return render(request, 'blog/profile.html', {
        'profile': profile_user,
        'page_obj': page_obj
    })


@login_required
def edit_profile(request):
    """Редактирование профиля пользователя."""
    form = UserEditForm(request.POST or None, instance=request.user)
    if form.is_valid():
        form.save()
        return redirect('blog:profile', username=request.user.username)
    return render(request, 'blog/user.html', {'form': form})


class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            'blog:profile',
            kwargs={'username': self.request.user.username}
        )


class PostUpdateView(LoginRequiredMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'
    pk_url_kwarg = 'post_id'

    def dispatch(self, request, *args, **kwargs):
        post = get_object_or_404(Post, pk=kwargs['post_id'])
        if post.author != request.user:
            return redirect('blog:post_detail', post_id=kwargs['post_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse(
            'blog:post_detail',
            kwargs={'post_id': self.object.pk}
        )


class PostDeleteView(LoginRequiredMixin, DeleteView):
    model = Post
    template_name = 'blog/create.html'
    pk_url_kwarg = 'post_id'

    def dispatch(self, request, *args, **kwargs):
        post = get_object_or_404(Post, pk=kwargs['post_id'])
        if post.author != request.user:
            return redirect('blog:post_detail', post_id=kwargs['post_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = PostForm(instance=self.object)
        return context

    def get_success_url(self):
        return reverse(
            'blog:profile',
            kwargs={'username': self.request.user.username}
        )


@login_required
def add_comment(request, post_id):
    """Добавление комментария к публикации."""
    post = get_object_or_404(Post, pk=post_id)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.post = post
        comment.save()
    return redirect('blog:post_detail', post_id=post_id)


class CommentUpdateView(LoginRequiredMixin, UpdateView):
    model = Comment
    form_class = CommentForm
    template_name = 'blog/comment.html'
    pk_url_kwarg = 'comment_id'

    def dispatch(self, request, *args, **kwargs):
        comment = get_object_or_404(Comment, pk=kwargs['comment_id'])
        if comment.author != request.user:
            return redirect('blog:post_detail', post_id=kwargs['post_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse(
            'blog:post_detail',
            kwargs={'post_id': self.kwargs['post_id']}
        )


class CommentDeleteView(LoginRequiredMixin, DeleteView):
    model = Comment
    template_name = 'blog/comment.html'
    pk_url_kwarg = 'comment_id'

    def dispatch(self, request, *args, **kwargs):
        comment = get_object_or_404(Comment, pk=kwargs['comment_id'])
        if comment.author != request.user:
            return redirect('blog:post_detail', post_id=kwargs['post_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse(
            'blog:post_detail',
            kwargs={'post_id': self.kwargs['post_id']}
        )


@login_required
def redirect_to_profile(request):
    """Редирект на страницу профиля после входа."""
    return redirect('blog:profile', username=request.user.username)
