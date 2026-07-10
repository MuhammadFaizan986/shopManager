from django.contrib import admin
from .models import Category, Product, StockHistory


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'supplier', 'purchase_price', 'selling_price', 'quantity', 'is_low_stock']
    list_filter = ['category', 'supplier']
    search_fields = ['name']


@admin.register(StockHistory)
class StockHistoryAdmin(admin.ModelAdmin):
    list_display = ['product', 'reason', 'quantity_change', 'quantity_after', 'user', 'timestamp']
    list_filter = ['reason']
    readonly_fields = ['timestamp']
