from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('sales/', views.sales_report, name='sales_report'),
    path('sales/pdf/', views.sales_report_pdf, name='sales_report_pdf'),
    path('inventory/', views.inventory_report, name='inventory_report'),
    path('profit-loss/', views.profit_loss, name='profit_loss'),
]
