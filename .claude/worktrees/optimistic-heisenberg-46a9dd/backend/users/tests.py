from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from .models import Role, Permission

User = get_user_model()

class PermissionTests(APITestCase):
    def setUp(self):
        
        self.view_user_perm = Permission.objects.create(code='users.view_user', description='')
        self.add_user_perm = Permission.objects.create(code='users.add_user', description='')
        
        self.admin_role = Role.objects.create(name='admin')
        self.admin_role.permissions.add(self.view_user_perm, self.add_user_perm)
      
        self.admin_user = User.objects.create_user(
            email='admin@example.com', phone='123456789', password='adminpass'
        )
        self.admin_user.roles.add(self.admin_role)
        
        self.normal_user = User.objects.create_user(
            email='user@example.com', phone='987654321', password='userpass'
        )
        
        self.client = APIClient()

    def test_admin_can_view_users(self):
       
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(reverse('user-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_normal_user_cannot_view_users(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get(reverse('user-list'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create_user(self):
        self.client.force_authenticate(user=self.admin_user)
        data = {
            'email': 'new@example.com',
            'phone': '111222333',
            'password': 'testpass123',
            'password2': 'testpass123'
        }
        response = self.client.post(reverse('user-list'), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_normal_user_cannot_create_user(self):
        self.client.force_authenticate(user=self.normal_user)
        data = {
            'email': 'new@example.com',
            'phone': '111222333',
            'password': 'testpass123',
            'password2': 'testpass123'
        }
        response = self.client.post(reverse('user-list'), data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

   