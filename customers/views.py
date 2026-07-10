from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Customer
from .forms import CustomerForm


@login_required
def customer_list(request):
    q = request.GET.get('q', '')
    customers = Customer.objects.all()
    if q:
        customers = customers.filter(name__icontains=q)
    return render(request, 'customers/customer_list.html', {'customers': customers, 'q': q})


@login_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    sales = customer.sale_set.prefetch_related('items').order_by('-date')
    return render(request, 'customers/customer_detail.html', {'customer': customer, 'sales': sales})


@login_required
def customer_add(request):
    form = CustomerForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Customer added.')
        return redirect('customers:customer_list')
    return render(request, 'customers/customer_form.html', {'form': form, 'title': 'Add Customer'})


@login_required
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    form = CustomerForm(request.POST or None, instance=customer)
    if form.is_valid():
        form.save()
        messages.success(request, 'Customer updated.')
        return redirect('customers:customer_detail', pk=pk)
    return render(request, 'customers/customer_form.html', {'form': form, 'title': 'Edit Customer', 'customer': customer})


@login_required
def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        customer.delete()
        messages.success(request, 'Customer deleted.')
        return redirect('customers:customer_list')
    return render(request, 'customers/customer_confirm_delete.html', {'customer': customer})
