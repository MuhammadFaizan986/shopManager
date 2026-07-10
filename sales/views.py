import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db import transaction
from django.utils import timezone
from inventory.models import Product, StockHistory
from customers.models import Customer
from .models import Sale, SaleItem


@login_required
def sale_list(request):
    sales = Sale.objects.select_related('customer', 'created_by').prefetch_related('items')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    customer_id = request.GET.get('customer', '')

    if date_from:
        sales = sales.filter(date__gte=date_from)
    if date_to:
        sales = sales.filter(date__lte=date_to)
    if customer_id:
        sales = sales.filter(customer_id=customer_id)

    customers = Customer.objects.all()
    return render(request, 'sales/sale_list.html', {
        'sales': sales,
        'customers': customers,
        'date_from': date_from,
        'date_to': date_to,
        'customer_id': customer_id,
    })


@login_required
def sale_detail(request, pk):
    sale = get_object_or_404(Sale.objects.prefetch_related('items__product'), pk=pk)
    return render(request, 'sales/sale_detail.html', {'sale': sale})


@login_required
def sale_create(request):
    customers = Customer.objects.all()
    products = Product.objects.filter(quantity__gt=0).select_related('category')
    product_data = {
        str(p.pk): {
            'name': p.name,
            'price': float(p.selling_price),
            'stock': p.quantity,
        }
        for p in products
    }

    if request.method == 'POST':
        customer_id = request.POST.get('customer') or None
        discount = request.POST.get('discount', '0') or '0'
        notes = request.POST.get('notes', '')
        item_data = request.POST.get('items_json', '[]')

        try:
            items = json.loads(item_data)
        except json.JSONDecodeError:
            messages.error(request, 'Invalid item data.')
            return redirect('sales:sale_create')

        if not items:
            messages.error(request, 'Add at least one product to the sale.')
            return redirect('sales:sale_create')

        with transaction.atomic():
            sale = Sale.objects.create(
                customer_id=customer_id,
                discount=discount,
                notes=notes,
                created_by=request.user,
            )
            for item in items:
                product = get_object_or_404(Product, pk=item['product_id'])
                qty = int(item['quantity'])
                price = float(item['unit_price'])

                if product.quantity < qty:
                    transaction.set_rollback(True)
                    messages.error(request, f'Not enough stock for {product.name}.')
                    return redirect('sales:sale_create')

                SaleItem.objects.create(
                    sale=sale,
                    product=product,
                    quantity=qty,
                    unit_price=price,
                    purchase_price=product.purchase_price,
                )
                before = product.quantity
                product.quantity -= qty
                product.save()
                StockHistory.objects.create(
                    product=product,
                    reason='sale',
                    quantity_change=-qty,
                    quantity_before=before,
                    quantity_after=product.quantity,
                    note=f'Sale {sale.invoice_number}',
                    user=request.user,
                )

        messages.success(request, f'Sale {sale.invoice_number} created successfully.')
        return redirect('sales:invoice_detail', pk=sale.pk)

    return render(request, 'sales/sale_create.html', {
        'customers': customers,
        'products': products,
        'product_data_json': json.dumps(product_data),
    })


@login_required
def invoice_detail(request, pk):
    sale = get_object_or_404(Sale.objects.prefetch_related('items__product'), pk=pk)
    return render(request, 'sales/invoice_detail.html', {'sale': sale})


@login_required
def invoice_pdf(request, pk):
    import io
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors

    sale = get_object_or_404(Sale.objects.prefetch_related('items__product'), pk=pk)

    buf = io.BytesIO()
    width, height = A4
    c = canvas.Canvas(buf, pagesize=A4)
    margin = 20 * mm
    y = height - margin

    # Header
    c.setFont('Helvetica-Bold', 18)
    c.drawString(margin, y, 'ShopManager')
    c.setFont('Helvetica', 10)
    c.drawString(margin, y - 6 * mm, 'Tax Invoice')

    c.setFont('Helvetica-Bold', 12)
    c.drawRightString(width - margin, y, sale.invoice_number)
    c.setFont('Helvetica', 10)
    c.drawRightString(width - margin, y - 6 * mm, f'Date: {sale.date.strftime("%d %b %Y")}')

    y -= 20 * mm

    # Bill To
    if sale.customer:
        c.setFont('Helvetica-Bold', 10)
        c.drawString(margin, y, 'Bill To:')
        c.setFont('Helvetica', 10)
        c.drawString(margin, y - 5 * mm, sale.customer.name)
        if sale.customer.phone:
            c.drawString(margin, y - 10 * mm, sale.customer.phone)
        y -= 18 * mm

    y -= 4 * mm

    # Table header
    col_widths = [10 * mm, 80 * mm, 20 * mm, 30 * mm, 30 * mm]
    col_x = [margin + sum(col_widths[:i]) for i in range(len(col_widths))]
    row_h = 7 * mm

    c.setFillColor(colors.HexColor('#f5f5f5'))
    c.rect(margin, y - row_h, width - 2 * margin, row_h, fill=1, stroke=1)
    c.setFillColor(colors.black)
    c.setFont('Helvetica-Bold', 9)
    headers = ['#', 'Product', 'Qty', 'Unit Price', 'Total']
    for i, h in enumerate(headers):
        if i >= 2:
            c.drawRightString(col_x[i] + col_widths[i] - 2 * mm, y - row_h + 2 * mm, h)
        else:
            c.drawString(col_x[i] + 2 * mm, y - row_h + 2 * mm, h)
    y -= row_h

    # Table rows
    c.setFont('Helvetica', 9)
    for idx, item in enumerate(sale.items.all(), 1):
        c.rect(margin, y - row_h, width - 2 * margin, row_h, fill=0, stroke=1)
        c.drawString(col_x[0] + 2 * mm, y - row_h + 2 * mm, str(idx))
        c.drawString(col_x[1] + 2 * mm, y - row_h + 2 * mm, item.product.name[:40])
        c.drawRightString(col_x[2] + col_widths[2] - 2 * mm, y - row_h + 2 * mm, str(item.quantity))
        c.drawRightString(col_x[3] + col_widths[3] - 2 * mm, y - row_h + 2 * mm, f'Rs. {item.unit_price}')
        c.drawRightString(col_x[4] + col_widths[4] - 2 * mm, y - row_h + 2 * mm, f'Rs. {item.line_total}')
        y -= row_h

    # Totals
    y -= 8 * mm
    c.setFont('Helvetica', 10)
    c.drawRightString(width - margin - 35 * mm, y, 'Subtotal:')
    c.drawRightString(width - margin, y, f'Rs. {sale.subtotal}')
    y -= 7 * mm
    if sale.discount:
        c.drawRightString(width - margin - 35 * mm, y, 'Discount:')
        c.drawRightString(width - margin, y, f'- Rs. {sale.discount}')
        y -= 7 * mm
    # Separator line above Grand Total
    c.setStrokeColor(colors.HexColor('#cccccc'))
    c.line(width - margin - 70 * mm, y + 4 * mm, width - margin, y + 4 * mm)
    c.setStrokeColor(colors.black)
    c.setFont('Helvetica-Bold', 11)
    c.drawRightString(width - margin - 35 * mm, y, 'Grand Total:')
    c.drawRightString(width - margin, y, f'Rs. {sale.grand_total}')

    # Notes
    if sale.notes:
        y -= 12 * mm
        c.setFont('Helvetica', 9)
        c.drawString(margin, y, f'Notes: {sale.notes}')

    # Footer
    c.setFont('Helvetica', 9)
    c.setFillColor(colors.HexColor('#888888'))
    c.drawCentredString(width / 2, margin, 'Thank you for your business!')

    c.save()
    pdf = buf.getvalue()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{sale.invoice_number}.pdf"'
    return response


@login_required
def sale_edit(request, pk):
    sale = get_object_or_404(Sale.objects.prefetch_related('items__product'), pk=pk)
    customers = Customer.objects.all()
    products = Product.objects.select_related('category')
    product_data = {
        str(p.pk): {
            'name': p.name,
            'price': float(p.selling_price),
            'stock': p.quantity,
        }
        for p in products
    }

    # Add back current sale quantities to show true available stock in the picker
    for item in sale.items.all():
        pid = str(item.product.pk)
        if pid in product_data:
            product_data[pid]['stock'] += item.quantity

    existing_items = [
        {
            'product_id': str(item.product.pk),
            'product_name': item.product.name,
            'quantity': item.quantity,
            'unit_price': float(item.unit_price),
        }
        for item in sale.items.all()
    ]

    if request.method == 'POST':
        customer_id = request.POST.get('customer') or None
        discount = request.POST.get('discount', '0') or '0'
        notes = request.POST.get('notes', '')
        item_data = request.POST.get('items_json', '[]')

        try:
            new_items = json.loads(item_data)
        except json.JSONDecodeError:
            messages.error(request, 'Invalid item data.')
            return redirect('sales:sale_edit', pk=pk)

        if not new_items:
            messages.error(request, 'Add at least one product to the sale.')
            return redirect('sales:sale_edit', pk=pk)

        with transaction.atomic():
            # Restore stock for all existing items
            for item in sale.items.all():
                item.product.quantity += item.quantity
                item.product.save()
                StockHistory.objects.create(
                    product=item.product,
                    reason='adjustment',
                    quantity_change=item.quantity,
                    quantity_before=item.product.quantity - item.quantity,
                    quantity_after=item.product.quantity,
                    note=f'Edit reversal for {sale.invoice_number}',
                    user=request.user,
                )

            # Remove old items
            sale.items.all().delete()

            # Update sale header
            sale.customer_id = customer_id
            sale.discount = discount
            sale.notes = notes
            sale.save()

            # Create new items and deduct stock
            for item in new_items:
                product = get_object_or_404(Product, pk=item['product_id'])
                qty = int(item['quantity'])
                price = float(item['unit_price'])

                if product.quantity < qty:
                    transaction.set_rollback(True)
                    messages.error(request, f'Not enough stock for {product.name}.')
                    return redirect('sales:sale_edit', pk=pk)

                SaleItem.objects.create(
                    sale=sale,
                    product=product,
                    quantity=qty,
                    unit_price=price,
                    purchase_price=product.purchase_price,
                )
                before = product.quantity
                product.quantity -= qty
                product.save()
                StockHistory.objects.create(
                    product=product,
                    reason='sale',
                    quantity_change=-qty,
                    quantity_before=before,
                    quantity_after=product.quantity,
                    note=f'Sale edit {sale.invoice_number}',
                    user=request.user,
                )

        messages.success(request, f'Sale {sale.invoice_number} updated successfully.')
        return redirect('sales:sale_detail', pk=sale.pk)

    return render(request, 'sales/sale_edit.html', {
        'sale': sale,
        'customers': customers,
        'products': products,
        'product_data_json': json.dumps(product_data),
        'existing_items_json': json.dumps(existing_items),
    })


@login_required
def sale_delete(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    if request.method == 'POST':
        sale.delete()
        messages.success(request, 'Sale deleted.')
        return redirect('sales:sale_list')
    return render(request, 'sales/sale_confirm_delete.html', {'sale': sale})


@login_required
def product_price_api(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return JsonResponse({'price': float(product.selling_price), 'stock': product.quantity})
