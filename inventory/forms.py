from django import forms
from .models import Product, Category, StockHistory


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'category', 'supplier', 'purchase_price', 'selling_price',
                  'quantity', 'low_stock_threshold', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']


class StockAddForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.all())
    quantity = forms.IntegerField(min_value=1, label='Quantity to Add')
    purchase_price = forms.DecimalField(
        max_digits=10, decimal_places=2, min_value=0,
        label='Purchase Price (Rs.)',
        help_text='Update the cost price for all current stock.',
    )
    selling_price = forms.DecimalField(
        max_digits=10, decimal_places=2, min_value=0,
        label='Selling Price (Rs.)',
        help_text='Update the selling price for all current stock.',
    )
    note = forms.CharField(max_length=300, required=False, label='Note (optional)')


class StockAdjustForm(forms.Form):
    ADJUST_CHOICES = [
        ('adjustment_add', 'Add'),
        ('adjustment_deduct', 'Deduct'),
        ('adjustment_correct', 'Set Correct Value'),
    ]
    product = forms.ModelChoiceField(queryset=Product.objects.all())
    adjust_type = forms.ChoiceField(choices=ADJUST_CHOICES)
    quantity = forms.IntegerField(min_value=0, label='Quantity')
    note = forms.CharField(max_length=300, required=False, label='Reason / Note')
