from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Product, Category, StockHistory
from .forms import ProductForm, CategoryForm, StockAddForm, StockAdjustForm
from suppliers.models import Supplier


# ── Products ──────────────────────────────────────────────────────────────────

@login_required
def product_list(request):
    q = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    low_stock = request.GET.get('low_stock', '')

    products = Product.objects.select_related('category', 'supplier').order_by('category__name', 'name')
    if q:
        products = products.filter(Q(name__icontains=q) | Q(description__icontains=q))
    if category_id:
        products = products.filter(category_id=category_id)
    if low_stock:
        products = [p for p in products if p.is_low_stock]

    palette = ['text-primary', 'text-success', 'text-danger', 'text-warning',
               'text-info', 'text-secondary']
    all_cats = list(Category.objects.order_by('name').values_list('name', flat=True))
    color_map = {name: palette[i % len(palette)] for i, name in enumerate(all_cats)}

    products = list(products)
    for p in products:
        p.category_color = color_map.get(p.category.name, '') if p.category else ''

    categories = Category.objects.all()
    return render(request, 'inventory/product_list.html', {
        'products': products,
        'categories': categories,
        'q': q,
        'category_id': category_id,
        'low_stock': low_stock,
    })


@login_required
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    history = product.stock_history.select_related('user').all()[:20]
    return render(request, 'inventory/product_detail.html', {'product': product, 'history': history})


@login_required
def product_detail_json(request, pk):
    product = get_object_or_404(Product, pk=pk)
    history = list(
        product.stock_history.select_related('user').order_by('-timestamp')[:10].values(
            'timestamp', 'reason', 'quantity_change', 'quantity_before', 'quantity_after', 'note', 'user__username'
        )
    )
    for h in history:
        h['timestamp'] = h['timestamp'].strftime('%d %b %Y %H:%M')
    return JsonResponse({
        'id': product.pk,
        'name': product.name,
        'category': str(product.category) if product.category else '—',
        'supplier': str(product.supplier) if product.supplier else '—',
        'purchase_price': float(product.purchase_price),
        'selling_price': float(product.selling_price),
        'profit_margin': round(float(product.profit_margin), 1),
        'quantity': product.quantity,
        'low_stock_threshold': product.low_stock_threshold,
        'is_low_stock': product.is_low_stock,
        'description': product.description or '',
        'edit_url': f'/inventory/{product.pk}/edit/',
        'delete_url': f'/inventory/{product.pk}/delete/',
        'history': history,
    })


@login_required
def product_edit_ajax(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            return JsonResponse({'ok': True})
        return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
    # GET — return product data + dropdown choices
    return JsonResponse({
        'id': product.pk,
        'name': product.name,
        'category_id': product.category_id or '',
        'supplier_id': product.supplier_id or '',
        'purchase_price': float(product.purchase_price),
        'selling_price': float(product.selling_price),
        'quantity': product.quantity,
        'low_stock_threshold': product.low_stock_threshold,
        'description': product.description,
        'categories': list(Category.objects.values('id', 'name')),
        'suppliers': list(Supplier.objects.values('id', 'name')),
    })


@login_required
@require_POST
def product_delete_ajax(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.delete()
    return JsonResponse({'ok': True})


@login_required
def product_add(request):
    form = ProductForm(request.POST or None)
    if form.is_valid():
        product = form.save()
        if product.quantity > 0:
            StockHistory.objects.create(
                product=product,
                reason='purchase',
                quantity_change=product.quantity,
                quantity_before=0,
                quantity_after=product.quantity,
                note='Initial stock on product creation',
                user=request.user,
            )
        messages.success(request, f'Product "{product.name}" added successfully.')
        return redirect('inventory:product_list')
    categories = Category.objects.all()
    return render(request, 'inventory/product_form.html', {
        'form': form,
        'title': 'Add Product',
        'categories': categories,
    })


@login_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)
    if form.is_valid():
        form.save()
        messages.success(request, 'Product updated.')
        return redirect('inventory:product_list')
    categories = Category.objects.all()
    return render(request, 'inventory/product_form.html', {
        'form': form,
        'title': 'Edit Product',
        'product': product,
        'categories': categories,
    })


@login_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Product deleted.')
        return redirect('inventory:product_list')
    return render(request, 'inventory/product_confirm_delete.html', {'product': product})


# ── Categories ────────────────────────────────────────────────────────────────

@login_required
def category_list(request):
    categories = Category.objects.all()
    return render(request, 'inventory/category_list.html', {'categories': categories})


@login_required
def category_add(request):
    next_url = request.GET.get('next', '') or request.POST.get('next', '')
    if next_url and not next_url.startswith('/'):
        next_url = ''
    form = CategoryForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Category added.')
        return redirect(next_url if next_url else 'inventory:category_list')
    return render(request, 'inventory/category_form.html', {'form': form, 'title': 'Add Category', 'next': next_url})


@login_required
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    form = CategoryForm(request.POST or None, instance=category)
    if form.is_valid():
        form.save()
        messages.success(request, 'Category updated.')
        return redirect('inventory:category_list')
    return render(request, 'inventory/category_form.html', {'form': form, 'title': 'Edit Category', 'category': category})


@login_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        category.delete()
        messages.success(request, 'Category deleted.')
        return redirect('inventory:category_list')
    return render(request, 'inventory/category_confirm_delete.html', {'category': category})


@login_required
def category_products_ajax(request, pk):
    """Return products for a category as JSON for the modal."""
    category = get_object_or_404(Category, pk=pk)
    products = Product.objects.filter(category=category).select_related('supplier').values(
        'id', 'name', 'quantity', 'purchase_price', 'selling_price', 'low_stock_threshold',
        'supplier__name',
    )
    data = []
    for p in products:
        data.append({
            'id': p['id'],
            'name': p['name'],
            'quantity': p['quantity'],
            'purchase_price': float(p['purchase_price']),
            'selling_price': float(p['selling_price']),
            'low_stock_threshold': p['low_stock_threshold'],
            'supplier': p['supplier__name'] or '—',
            'is_low_stock': p['quantity'] <= p['low_stock_threshold'],
        })
    return JsonResponse({'category': category.name, 'products': data})


@login_required
def category_add_ajax(request):
    """Quick-add a category from the product form modal. Returns JSON."""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            return JsonResponse({'error': 'Name is required.'}, status=400)
        if Category.objects.filter(name__iexact=name).exists():
            return JsonResponse({'error': f'Category "{name}" already exists.'}, status=400)
        category = Category.objects.create(name=name)
        return JsonResponse({'id': category.pk, 'name': category.name})
    return JsonResponse({'error': 'Invalid request.'}, status=405)


# ── Stock ─────────────────────────────────────────────────────────────────────

@login_required
def stock_add(request):
    initial = {}
    product_id = request.GET.get('product') or request.POST.get('product')
    preselected = None
    if product_id:
        try:
            preselected = Product.objects.get(pk=product_id)
            initial['product'] = preselected
            initial['purchase_price'] = preselected.purchase_price
            initial['selling_price'] = preselected.selling_price
        except Product.DoesNotExist:
            pass

    # Build JSON data for all products so JS can update price fields on change
    all_products = {
        str(p.pk): {
            'purchase_price': float(p.purchase_price),
            'selling_price': float(p.selling_price),
        }
        for p in Product.objects.all()
    }

    form = StockAddForm(request.POST or None, initial=initial)
    if form.is_valid():
        product = form.cleaned_data['product']
        qty = form.cleaned_data['quantity']
        new_purchase = form.cleaned_data['purchase_price']
        new_selling = form.cleaned_data['selling_price']
        note = form.cleaned_data.get('note', '')

        before = product.quantity
        product.quantity += qty
        product.purchase_price = new_purchase
        product.selling_price = new_selling
        product.save()

        StockHistory.objects.create(
            product=product,
            reason='purchase',
            quantity_change=qty,
            quantity_before=before,
            quantity_after=product.quantity,
            note=note or f'Price updated: buy Rs.{new_purchase} / sell Rs.{new_selling}',
            user=request.user,
        )
        messages.success(request, f'Added {qty} units to "{product.name}". Prices updated.')
        return redirect('inventory:product_list')

    import json
    return render(request, 'inventory/stock_add.html', {
        'form': form,
        'preselected': preselected,
        'all_products_json': json.dumps(all_products),
    })


@login_required
@require_POST
def stock_add_ajax(request):
    product = get_object_or_404(Product, pk=request.POST.get('product_id'))
    try:
        qty = int(request.POST.get('quantity', 0))
        new_purchase = float(request.POST.get('purchase_price', 0))
        new_selling = float(request.POST.get('selling_price', 0))
    except (ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'Invalid values.'}, status=400)

    if qty < 1:
        return JsonResponse({'ok': False, 'error': 'Quantity must be at least 1.'}, status=400)
    if new_purchase < 0 or new_selling < 0:
        return JsonResponse({'ok': False, 'error': 'Prices cannot be negative.'}, status=400)

    note = request.POST.get('note', '').strip()
    before = product.quantity
    product.quantity += qty
    product.purchase_price = new_purchase
    product.selling_price = new_selling
    product.save()

    StockHistory.objects.create(
        product=product,
        reason='purchase',
        quantity_change=qty,
        quantity_before=before,
        quantity_after=product.quantity,
        note=note or f'Price updated: buy Rs.{new_purchase} / sell Rs.{new_selling}',
        user=request.user,
    )
    return JsonResponse({'ok': True, 'new_quantity': product.quantity})


@login_required
def stock_adjust(request):
    form = StockAdjustForm(request.POST or None)
    if form.is_valid():
        product = form.cleaned_data['product']
        adjust_type = form.cleaned_data['adjust_type']
        qty = form.cleaned_data['quantity']
        note = form.cleaned_data.get('note', '')
        before = product.quantity

        if adjust_type == 'adjustment_add':
            product.quantity += qty
        elif adjust_type == 'adjustment_deduct':
            product.quantity = max(0, product.quantity - qty)
        else:
            product.quantity = qty

        product.save()
        StockHistory.objects.create(
            product=product,
            reason=adjust_type,
            quantity_change=product.quantity - before,
            quantity_before=before,
            quantity_after=product.quantity,
            note=note,
            user=request.user,
        )
        messages.success(request, f'Stock adjusted for {product.name}.')
        return redirect('inventory:stock_history')
    return render(request, 'inventory/stock_adjust.html', {'form': form})


@login_required
def stock_history_ajax(request):
    product_id = request.GET.get('product', '')
    qs = StockHistory.objects.select_related('product', 'user').order_by('-timestamp')
    if product_id:
        qs = qs.filter(product_id=product_id)
    data = [
        {
            'timestamp': h.timestamp.strftime('%d %b %Y %H:%M'),
            'product': h.product.name,
            'reason': h.get_reason_display(),
            'quantity_change': h.quantity_change,
            'quantity_before': h.quantity_before,
            'quantity_after': h.quantity_after,
            'note': h.note or '',
            'user': h.user.username if h.user else '',
        }
        for h in qs[:100]
    ]
    return JsonResponse({'history': data})


@login_required
def stock_history(request):
    product_id = request.GET.get('product', '')
    history = StockHistory.objects.select_related('product', 'user').all()
    if product_id:
        history = history.filter(product_id=product_id)
    products = Product.objects.all()
    return render(request, 'inventory/stock_history.html', {
        'history': history,
        'products': products,
        'product_id': product_id,
    })
