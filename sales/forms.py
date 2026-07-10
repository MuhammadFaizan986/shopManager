from django import forms
from .models import Sale, SaleItem
from customers.models import Customer
from inventory.models import Product


class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = ['customer', 'discount', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class SaleItemForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.filter(quantity__gt=0))
    quantity = forms.IntegerField(min_value=1)
    unit_price = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0)
