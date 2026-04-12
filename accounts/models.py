from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Administrador'),
        ('mecanico', 'Mecânico'),
        ('recepcionista', 'Recepcionista'),
    ]
    role = models.CharField('Perfil', max_length=20, choices=ROLE_CHOICES, default='recepcionista')
    telefone = models.CharField('Telefone', max_length=20, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    class Meta:
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def is_admin_role(self):
        return self.role == 'admin'

    @property
    def is_mecanico_role(self):
        return self.role == 'mecanico'
