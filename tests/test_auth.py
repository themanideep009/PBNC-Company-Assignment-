"""Tests for auth endpoints: register and login."""

import pytest


class TestRegister:
    """Tests for POST /auth/register."""

    def test_register_success(self, client):
        response = client.post("/auth/register", json={
            "email": "newuser@example.com",
            "password": "securepass123",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["role"] == "user"
        assert "id" in data
        assert "hashed_password" not in data  # Never leak password hash

    def test_register_duplicate_email(self, client):
        # Register once
        client.post("/auth/register", json={
            "email": "duplicate@example.com",
            "password": "password123",
        })
        # Register again with same email
        response = client.post("/auth/register", json={
            "email": "duplicate@example.com",
            "password": "password456",
        })
        assert response.status_code == 409

    def test_register_invalid_email(self, client):
        response = client.post("/auth/register", json={
            "email": "not-an-email",
            "password": "password123",
        })
        assert response.status_code == 422

    def test_register_short_password(self, client):
        response = client.post("/auth/register", json={
            "email": "shortpw@example.com",
            "password": "short",
        })
        assert response.status_code == 422


class TestLogin:
    """Tests for POST /auth/login."""

    def test_login_success(self, client):
        # Register first
        client.post("/auth/register", json={
            "email": "logintest@example.com",
            "password": "securepass123",
        })
        # Login
        response = client.post("/auth/login", json={
            "email": "logintest@example.com",
            "password": "securepass123",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        client.post("/auth/register", json={
            "email": "wrongpw@example.com",
            "password": "correctpassword",
        })
        response = client.post("/auth/login", json={
            "email": "wrongpw@example.com",
            "password": "wrongpassword",
        })
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        response = client.post("/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "anypassword",
        })
        assert response.status_code == 401


class TestProtectedEndpoints:
    """Test that endpoints require authentication."""

    def test_documents_requires_auth(self, client):
        response = client.get("/documents")
        assert response.status_code == 403  # No bearer token

    def test_documents_with_invalid_token(self, client):
        response = client.get(
            "/documents",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401

    def test_healthz_no_auth_required(self, client):
        response = client.get("/healthz")
        assert response.status_code == 200
