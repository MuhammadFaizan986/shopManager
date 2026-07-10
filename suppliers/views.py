from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Supplier
from .forms import SupplierForm


@login_required
def supplier_list(request):
    q = request.GET.get('q', '')
    suppliers = Supplier.objects.all()
    if q:
        suppliers = suppliers.filter(name__icontains=q)
    return render(request, 'suppliers/supplier_list.html', {'suppliers': suppliers, 'q': q})

 
@login_required
def supplier_detail(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    products = supplier.product_set.all()
    return render(request, 'suppliers/supplier_detail.html', {'supplier': supplier, 'products': products})


@login_required
def supplier_add(request):
    next_url = request.GET.get('next', '') or request.POST.get('next', '')
    if next_url and not next_url.startswith('/'):
        next_url = ''

    form = SupplierForm(request.POST or None)
    if form.is_valid():
        supplier = form.save()
        messages.success(request, 'Supplier added successfully.')
        if next_url:
            return redirect(f'{next_url}?new_supplier={supplier.pk}')
        return redirect('suppliers:supplier_list')
    return render(request, 'suppliers/supplier_form.html', {
        'form': form,
        'title': 'Add Supplier',
        'next': next_url,
    })


@login_required
def supplier_edit(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    form = SupplierForm(request.POST or None, instance=supplier)
    if form.is_valid():
        form.save()
        messages.success(request, 'Supplier updated successfully.')
        return redirect('suppliers:supplier_detail', pk=pk)
    return render(request, 'suppliers/supplier_form.html', {'form': form, 'title': 'Edit Supplier', 'supplier': supplier})


@login_required
def supplier_delete(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        supplier.delete()
        messages.success(request, 'Supplier deleted.')
        return redirect('suppliers:supplier_list')
    return render(request, 'suppliers/supplier_confirm_delete.html', {'supplier': supplier})
