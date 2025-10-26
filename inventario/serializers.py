from rest_framework import serializers
from .models import Usuario, Producto, Factura, DetalleFactura



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
        fields = '__all__'

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
