from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # Products
    path('', views.product_list, name='product_list'),
    path('add/', views.product_add, name='product_add'),
    path('<int:pk>/', views.product_detail, name='product_detail'),
    path('<int:pk>/json/', views.product_detail_json, name='product_detail_json'),
    path('<int:pk>/edit-ajax/', views.product_edit_ajax, name='product_edit_ajax'),
    path('<int:pk>/delete-ajax/', views.product_delete_ajax, name='product_delete_ajax'),
    path('<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('<int:pk>/delete/', views.product_delete, name='product_delete'),
    # Categories
    path('categories/', views.category_list, name='category_list'),
    path('categories/add/', views.category_add, name='category_add'),
    path('categories/<int:pk>/edit/', views.category_edit, name='category_edit'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),
    path('categories/ajax/add/', views.category_add_ajax, name='category_add_ajax'),
    path('categories/<int:pk>/products/', views.category_products_ajax, name='category_products_ajax'),
    # Stock
    path('stock/add/', views.stock_add, name='stock_add'),
    path('stock/add-ajax/', views.stock_add_ajax, name='stock_add_ajax'),
    path('stock/adjust/', views.stock_adjust, name='stock_adjust'),
    path('stock/history/', views.stock_history, name='stock_history'),
    path('stock/history/json/', views.stock_history_ajax, name='stock_history_ajax'),
]
