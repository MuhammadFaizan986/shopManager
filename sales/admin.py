from django.contrib import admin
from .models import Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ['line_total', 'line_profit']


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'customer', 'date', 'grand_total', 'created_by']
    list_filter = ['date']
    search_fields = ['invoice_number']
    inlines = [SaleItemInline]
    readonly_fields = ['invoice_number', 'date']
