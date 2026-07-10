from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    path('', views.sale_list, name='sale_list'),
    path('new/', views.sale_create, name='sale_create'),
    path('<int:pk>/', views.sale_detail, name='sale_detail'),
    path('<int:pk>/edit/', views.sale_edit, name='sale_edit'),
    path('<int:pk>/delete/', views.sale_delete, name='sale_delete'),
    path('<int:pk>/invoice/', views.invoice_detail, name='invoice_detail'),
    path('<int:pk>/invoice/pdf/', views.invoice_pdf, name='invoice_pdf'),
    path('api/product/<int:pk>/', views.product_price_api, name='product_price_api'),
]
