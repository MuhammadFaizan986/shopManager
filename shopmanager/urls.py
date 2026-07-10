from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(pattern_name='reports:dashboard'), name='home'),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('inventory/', include('inventory.urls', namespace='inventory')),
    path('suppliers/', include('suppliers.urls', namespace='suppliers')),
    path('customers/', include('customers.urls', namespace='customers')),
    path('sales/', include('sales.urls', namespace='sales')),
    path('reports/', include('reports.urls', namespace='reports')),
]

handler404 = 'shopmanager.views.error_404'
handler500 = 'shopmanager.views.error_500'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
