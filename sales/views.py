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
    from reportlab.lib.units import mm
    from reportlab.lib import colors

    sale = get_object_or_404(Sale.objects.prefetch_related('items__product'), pk=pk)

    # 58mm receipt format
    receipt_width = 58 * mm
    receipt_height = 297 * mm
    pagesize = (receipt_width, receipt_height)

    buf = io.BytesIO()
    width, height = pagesize
    c = canvas.Canvas(buf, pagesize=pagesize)
    margin = 1.5 * mm
    y = height - (margin + 3 * mm)

    # Shop Name Header
    c.setFont('Helvetica-Bold', 11)
    c.drawCentredString(width / 2, y, 'UmairZubair')
    y -= 4 * mm

    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(width / 2, y, 'Tailoring Shop')
    y -= 4 * mm

    c.setFont('Helvetica', 7)
    c.drawCentredString(width / 2, y, '0322-4266252, 0316-4173209')
    y -= 3.5 * mm

    # Separator
    c.setLineWidth(1)
    c.setStrokeColor(colors.black)
    c.line(margin, y, width - margin, y)
    y -= 3.5 * mm

    # Invoice details (centered)
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(width / 2, y, sale.invoice_number)
    y -= 3.5 * mm

    c.setFont('Helvetica', 8)
    c.drawCentredString(width / 2, y, sale.date.strftime('%d %b %Y'))
    y -= 4.5 * mm

    # Customer info
    if sale.customer:
        c.setFont('Helvetica-Bold', 7)
        c.drawString(margin, y, 'Customer:')
        c.setFont('Helvetica', 7)
        y -= 3 * mm
        c.drawString(margin + 1 * mm, y, sale.customer.name[:26])
        if sale.customer.phone:
            y -= 3 * mm
            c.drawString(margin + 1 * mm, y, sale.customer.phone)
        y -= 4 * mm
    else:
        y -= 2.5 * mm

    # Separator
    c.setLineWidth(0.5)
    c.setStrokeColor(colors.HexColor('#cccccc'))
    c.line(margin, y, width - margin, y)
    y -= 3 * mm

    # Items header
    c.setFont('Helvetica-Bold', 10.5)
    c.drawString(margin, y, 'Item')
    c.drawString(margin + 27 * mm, y, 'Qty')
    c.drawRightString(width - margin - 0.5 * mm, y, 'Price')
    y -= 3.5 * mm

    # Items separator
    c.setLineWidth(0.5)
    c.setStrokeColor(colors.HexColor('#cccccc'))
    c.line(margin, y, width - margin, y)
    y -= 3.5 * mm

    # Items list
    c.setFont('Helvetica', 10)
    for item in sale.items.all():
        # Product name
        product_name = item.product.name[:16]
        c.drawString(margin, y, product_name)

        # Qty and Total
        c.drawString(margin + 27 * mm, y, str(item.quantity))
        c.drawRightString(width - margin - 0.5 * mm, y, f'Rs.{item.line_total:.2f}')
        y -= 3.2 * mm

        # Unit price (smaller, black)
        c.setFont('Helvetica', 8)
        c.setFillColor(colors.black)
        c.drawString(margin + 1.5 * mm, y, f'@ Rs.{item.unit_price:.2f}')
        c.setFont('Helvetica', 10)
        y -= 3.2 * mm

        # Separator line between items
        c.setLineWidth(0.3)
        c.setStrokeColor(colors.HexColor('#e0e0e0'))
        c.line(margin, y, width - margin, y)
        y -= 2 * mm

    # Totals separator
    y -= 4 * mm
    c.setLineWidth(0.5)
    c.setStrokeColor(colors.HexColor('#cccccc'))
    c.line(margin, y, width - margin, y)
    y -= 3.5 * mm

    # Subtotal
    c.setFont('Helvetica', 8)
    c.drawString(margin, y, 'Subtotal')
    c.drawRightString(width - margin - 0.5 * mm, y, f'Rs.{sale.subtotal:.2f}')
    y -= 3.5 * mm

    # Discount
    if sale.discount and float(sale.discount) > 0:
        c.drawString(margin, y, 'Discount')
        c.drawRightString(width - margin - 0.5 * mm, y, f'-Rs.{sale.discount:.2f}')
        y -= 3.5 * mm

    # Grand Total
    y -= 2 * mm
    c.setLineWidth(1)
    c.setStrokeColor(colors.black)
    c.line(margin, y, width - margin, y)
    y -= 3.5 * mm

    c.setFont('Helvetica-Bold', 10)
    c.setFillColor(colors.black)
    c.drawString(margin, y, 'Total')
    c.drawRightString(width - margin - 0.5 * mm, y, f'Rs.{sale.grand_total:.2f}')
    y -= 3.5 * mm

    c.setLineWidth(1)
    c.line(margin, y, width - margin, y)
    y -= 4 * mm

    # Notes
    if sale.notes and sale.notes.strip():
        c.setFont('Helvetica', 6)
        c.setFillColor(colors.HexColor('#666666'))
        notes_text = sale.notes[:35]
        c.drawString(margin, y, f'Note: {notes_text}')
        y -= 3.5 * mm

    # Footer message
    y -= 2.5 * mm
    c.setFont('Helvetica-Bold', 8)
    c.setFillColor(colors.black)
    c.drawCentredString(width / 2, y, 'Thank You!')
    y -= 3 * mm

    c.setFont('Helvetica', 6)
    c.setFillColor(colors.HexColor('#888888'))
    c.drawCentredString(width / 2, y, 'Visit Again')

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
