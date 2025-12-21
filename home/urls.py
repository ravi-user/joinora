from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('services/', views.services, name='services'),
    path('create-order/', views.create_order, name='create_order'),
    path('handle-payment/', views.handle_payment, name='handle_payment'),
    path('success/', views.payment_success, name='payment_success'),
]
