from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Count
from django.utils import timezone
from datetime import timedelta, date
from collections import defaultdict
import json

from sales.models import Sale, SaleItem
from inventory.models import Product, StockHistory
from customers.models import Customer


def _date_range_from_request(request, default_days=30):
    today = date.today()
    date_from = request.GET.get('date_from', '') or (today - timedelta(days=default_days)).isoformat()
    date_to = request.GET.get('date_to', '') or today.isoformat()
    return date_from, date_to


@login_required
def dashboard(request):
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_month = today.replace(day=1)

    qs = Sale.objects.select_related('customer').prefetch_related('items').order_by('-date', '-created_at')

    daily_sales   = [s for s in qs if s.date == today]
    weekly_sales  = [s for s in qs if s.date >= start_of_week]
    monthly_sales = [s for s in qs if s.date >= start_of_month]

    all_products = Product.objects.all()
    low_stock_products = [p for p in all_products if p.is_low_stock]
    recent_sales = list(qs[:7])

    daily_revenue = sum(s.grand_total for s in daily_sales)
    weekly_revenue = sum(s.grand_total for s in weekly_sales)
    monthly_revenue = sum(s.grand_total for s in monthly_sales)

    daily_items = sum(s.items.count() for s in daily_sales)
    weekly_items = sum(s.items.count() for s in weekly_sales)
    monthly_items = sum(s.items.count() for s in monthly_sales)

    total_inventory_value = sum(p.selling_price * p.quantity for p in all_products)

    return render(request, 'reports/dashboard.html', {
        'daily_sales':    daily_sales,
        'weekly_sales':   weekly_sales,
        'monthly_sales':  monthly_sales,
        'daily_revenue':  daily_revenue,
        'weekly_revenue': weekly_revenue,
        'monthly_revenue': monthly_revenue,
        'daily_orders': len(daily_sales),
        'weekly_orders': len(weekly_sales),
        'monthly_orders': len(monthly_sales),
        'daily_items': daily_items,
        'weekly_items': weekly_items,
        'monthly_items': monthly_items,
        'total_products': all_products.count(),
        'total_customers': Customer.objects.count(),
        'total_inventory_value': total_inventory_value,
        'low_stock_count': len(low_stock_products),
        'low_stock_products': low_stock_products[:5],
        'recent_sales': recent_sales,
    })


@login_required
def sales_report(request):
    date_from, date_to = _date_range_from_request(request)
    period = request.GET.get('period', 'daily')

    sales = list(Sale.objects.filter(date__gte=date_from, date__lte=date_to).prefetch_related('items').order_by('date'))

    total_revenue = sum(s.grand_total for s in sales)
    total_profit = sum(s.total_profit for s in sales)
    total_sales = len(sales)

    if period == 'monthly':
        # Group in Python to avoid SQLite TruncMonth timezone issues
        month_groups = defaultdict(int)
        for s in sales:
            key = str(s.date)[:7]  # 'YYYY-MM'
            month_groups[key] += 1
        chart_labels = json.dumps(sorted(month_groups.keys()))
        chart_values = json.dumps([month_groups[k] for k in sorted(month_groups.keys())])
    else:
        # Daily — use .values('date') directly instead of TruncDate
        daily_qs = (
            Sale.objects
            .filter(date__gte=date_from, date__lte=date_to)
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )
        labels = [r['date'].strftime('%d %b') for r in daily_qs]
        values = [r['count'] for r in daily_qs]
        chart_labels = json.dumps(labels)
        chart_values = json.dumps(values)

    return render(request, 'reports/sales_report.html', {
        'sales': sales,
        'date_from': date_from,
        'date_to': date_to,
        'period': period,
        'total_revenue': total_revenue,
        'total_profit': total_profit,
        'total_sales': total_sales,
        'chart_labels': chart_labels,
        'chart_values': chart_values,
    })


@login_required
def sales_report_pdf(request):
    import io
    from django.http import HttpResponse
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors

    date_from, date_to = _date_range_from_request(request)
    sales = list(Sale.objects.filter(date__gte=date_from, date__lte=date_to).prefetch_related('items').order_by('date'))

    total_revenue = sum(s.grand_total for s in sales)
    total_profit = sum(s.total_profit for s in sales)

    buf = io.BytesIO()
    width, height = A4
    c = canvas.Canvas(buf, pagesize=A4)
    margin = 20 * mm
    y = height - margin

    # Header
    c.setFont('Helvetica-Bold', 16)
    c.drawString(margin, y, 'Sales Report')
    c.setFont('Helvetica', 10)
    c.drawString(margin, y - 6 * mm, f'Period: {date_from}  to  {date_to}')
    c.drawRightString(width - margin, y, f'Total Sales: {len(sales)}')
    c.drawRightString(width - margin, y - 6 * mm, f'Revenue: Rs. {total_revenue}    Profit: Rs. {total_profit}')

    y -= 18 * mm

    # Table header
    col_widths = [42 * mm, 28 * mm, 45 * mm, 18 * mm, 28 * mm, 28 * mm]
    col_x = [margin + sum(col_widths[:i]) for i in range(len(col_widths))]
    row_h = 7 * mm
    headers = ['Invoice', 'Date', 'Customer', 'Items', 'Total', 'Profit']

    c.setFillColor(colors.HexColor('#f5f5f5'))
    c.rect(margin, y - row_h, width - 2 * margin, row_h, fill=1, stroke=1)
    c.setFillColor(colors.black)
    c.setFont('Helvetica-Bold', 9)
    for i, h in enumerate(headers):
        if i >= 3:
            c.drawRightString(col_x[i] + col_widths[i] - 2 * mm, y - row_h + 2 * mm, h)
        else:
            c.drawString(col_x[i] + 2 * mm, y - row_h + 2 * mm, h)
    y -= row_h

    c.setFont('Helvetica', 9)
    for sale in sales:
        if y < margin + row_h:
            c.showPage()
            y = height - margin
        c.rect(margin, y - row_h, width - 2 * margin, row_h, fill=0, stroke=1)
        c.drawString(col_x[0] + 2 * mm, y - row_h + 2 * mm, sale.invoice_number)
        c.drawString(col_x[1] + 2 * mm, y - row_h + 2 * mm, sale.date.strftime('%d %b %Y'))
        customer = str(sale.customer) if sale.customer else 'Walk-in'
        c.drawString(col_x[2] + 2 * mm, y - row_h + 2 * mm, customer[:22])
        c.drawRightString(col_x[3] + col_widths[3] - 2 * mm, y - row_h + 2 * mm, str(sale.items.count()))
        c.drawRightString(col_x[4] + col_widths[4] - 2 * mm, y - row_h + 2 * mm, f'Rs. {sale.grand_total}')
        c.setFillColor(colors.HexColor('#198754'))
        c.drawRightString(col_x[5] + col_widths[5] - 2 * mm, y - row_h + 2 * mm, f'Rs. {sale.total_profit}')
        c.setFillColor(colors.black)
        y -= row_h

    # Totals row
    y -= 4 * mm
    c.setFont('Helvetica-Bold', 10)
    c.drawRightString(col_x[4] + col_widths[4] - 2 * mm, y, f'Rs. {total_revenue}')
    c.setFillColor(colors.HexColor('#198754'))
    c.drawRightString(col_x[5] + col_widths[5] - 2 * mm, y, f'Rs. {total_profit}')
    c.setFillColor(colors.black)
    c.drawRightString(col_x[3] + col_widths[3] - 2 * mm, y, 'Total:')

    c.save()
    pdf = buf.getvalue()
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="sales_report_{date_from}_to_{date_to}.pdf"'
    return response


@login_required
def inventory_report(request):
    products = list(Product.objects.select_related('category', 'supplier').all())
    low_stock = [p for p in products if p.is_low_stock]

    total_stock_value = sum(p.purchase_price * p.quantity for p in products)
    total_retail_value = sum(p.selling_price * p.quantity for p in products)

    return render(request, 'reports/inventory_report.html', {
        'products': products,
        'low_stock': low_stock,
        'total_stock_value': total_stock_value,
        'total_retail_value': total_retail_value,
    })


@login_required
def profit_loss(request):
    date_from, date_to = _date_range_from_request(request)

    sales = list(Sale.objects.filter(date__gte=date_from, date__lte=date_to).prefetch_related('items__product'))

    total_revenue = sum(s.grand_total for s in sales)
    total_cost = sum(
        item.purchase_price * item.quantity
        for sale in sales
        for item in sale.items.all()
    )
    gross_profit = total_revenue - total_cost

    # Product breakdown — aggregate in Python to avoid ORM Decimal complexity
    breakdown = defaultdict(lambda: {'revenue': 0, 'cost': 0, 'qty': 0})
    for sale in sales:
        for item in sale.items.all():
            name = item.product.name
            breakdown[name]['revenue'] += item.unit_price * item.quantity
            breakdown[name]['cost'] += item.purchase_price * item.quantity
            breakdown[name]['qty'] += item.quantity

    product_breakdown = sorted(
        [
            {
                'product__name': name,
                'revenue': data['revenue'],
                'cost': data['cost'],
                'qty': data['qty'],
                'profit': data['revenue'] - data['cost'],
            }
            for name, data in breakdown.items()
        ],
        key=lambda x: x['revenue'],
        reverse=True,
    )

    return render(request, 'reports/profit_loss.html', {
        'date_from': date_from,
        'date_to': date_to,
        'total_revenue': total_revenue,
        'total_cost': total_cost,
        'gross_profit': gross_profit,
        'product_breakdown': product_breakdown,
    })
