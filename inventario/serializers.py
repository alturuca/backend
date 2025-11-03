from rest_framework import serializers
from .models import Usuario, Producto, Factura, DetalleFactura, IngresoProducto, DetalleIngresoProducto
from decimal import Decimal


"""
Este es el serializador del Usuario
"""
class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'rol', 'password']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data):
        return Usuario.objects.create_user(**validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

"""
Este es el seralizador del prodcuto
"""

class ProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Producto
        fields = ['sku','nombre', 'descripcion', 'precio_venta', 'precio_compra', 'stock']

"""
Este es el serializador de venta
"""

class DetalleFacturaSerializer(serializers.ModelSerializer):
    class Meta:
        model = DetalleFactura
        exclude = ['factura']

class FacturaSerializer(serializers.ModelSerializer):
    detalles = DetalleFacturaSerializer(many=True)

    class Meta:
        model = Factura
        fields = ['numero', 'cliente', 'fecha', 'detalles']
        read_only_fields = ['fecha']

    def create(self, validated_data):
        detalles_data = validated_data.pop('detalles')
        factura = Factura.objects.create(**validated_data)
        for detalle in detalles_data:
            DetalleFactura.objects.create(factura=factura, **detalle)
        return factura


"""
Este es el serializador de compra de producto
"""

class DetalleIngresoProductoSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(write_only=True)  # ✅ solo para entrada
    producto_sku = serializers.SerializerMethodField(read_only=True)  # ✅ para salida

    

    class Meta:
        model = DetalleIngresoProducto
        fields = ['sku', 'producto_sku' ,'cantidad', 'precio_compra', 'precio_venta']
    
    def get_producto_sku(self, obj):
        return obj.producto.sku  # ✅ devuelve el SKU del producto relacionado


    def validate_sku(self, value):
        try:
            Producto.objects.get(sku=value)
        except Producto.DoesNotExist:
            raise serializers.ValidationError("Producto con ese SKU no existe.")
        return value

    def create(self, validated_data):
        sku = validated_data.pop('sku')
        producto = Producto.objects.get(sku=sku)
        detalle = DetalleIngresoProducto.objects.create(producto=producto, **validated_data)

       
        return detalle
class IngresoProductoSerializer(serializers.ModelSerializer):
    detalles = DetalleIngresoProductoSerializer(many=True)

    class Meta:
        model = IngresoProducto
        fields = ['id','fecha', 'proveedor', 'detalles']
        read_only_fields = ['fecha']

    def create(self, validated_data):
        detalles_data = validated_data.pop('detalles')
        ingreso = IngresoProducto.objects.create(**validated_data)
        
        for detalle_data in detalles_data:
            sku = detalle_data.pop('sku')
            cantidad = detalle_data.get('cantidad', 0)
            precio_compra = detalle_data.get('precio_compra', Decimal('0.00') )
            precio_venta = round( Decimal('1.4') * precio_compra, 2)
            producto = Producto.objects.get(sku=sku)

            DetalleIngresoProducto.objects.create(
                ingreso=ingreso, 
                producto=producto, 
                cantidad=cantidad,  
                precio_compra=precio_compra,
                precio_venta=precio_venta
                )

            # Actualizar stock
            producto.stock += cantidad
            producto.save()

            # (Opcional) Guardar precio de 
            producto.precio_compra = precio_compra
            producto.precio_venta = precio_venta
            
            producto.save()

        return ingreso