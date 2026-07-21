from django.db import models
from django.contrib.auth.models import User
from customers.models import Customer
from inventory.models import Product


class Sale(models.Model):
    invoice_number = models.CharField(max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            last = Sale.objects.order_by('-id').first()
            next_id = (last.id + 1) if last else 1
            self.invoice_number = f'INV-{next_id:05d}'
        super().save(*args, **kwargs)

    def __str__(self):
        return self.invoice_number

    @property
    def subtotal(self):
        return sum(item.line_total for item in self.items.all())

    @property
    def grand_total(self):
        return self.subtotal - self.discount

    @property
    def total_profit(self):
        return sum(item.line_profit for item in self.items.all())


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    @property
    def line_profit(self):
        return (self.unit_price - self.purchase_price) * self.quantity
