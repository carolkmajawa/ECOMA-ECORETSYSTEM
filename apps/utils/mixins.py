class SwaggerViewSetMixin:
    """Mixin to handle Swagger/DRF-YASG requests"""
    
    def get_queryset(self):
        # Override this in child classes
        return super().get_queryset()
    
    def get_swagger_queryset(self):
        """Return empty queryset for Swagger"""
        return self.model.objects.none()