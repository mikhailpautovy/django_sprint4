from django.contrib.auth.forms import UserCreationForm
from django.urls import path
from django.views.generic import CreateView
from django.urls import reverse_lazy

urlpatterns = [
    path('', CreateView.as_view(
        template_name='registration/registration_form.html',
        form_class=UserCreationForm,
        success_url=reverse_lazy('blog:index'),
    ), name='registration'),
]
