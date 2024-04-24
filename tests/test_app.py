import pytest
from httpx import AsyncClient
from fastapi import FastAPI, status
from sqlalchemy.ext.asyncio import AsyncSession
from ..main import app, get_db  # Замініть на вірний шлях до вашого FastAPI app і get_db

@pytest.mark.asyncio
async def test_register_user_existing_email():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Спочатку реєструємо користувача
        await ac.post("/register/", json={"email": "user@example.com", "password": "password"})
        # Спроба реєстрації з тією ж email
        response = await ac.post("/register/", json={"email": "user@example.com", "password": "password"})
        assert response.status_code == 409
        assert "already registered" in response.json()["detail"]

@pytest.mark.asyncio
async def test_login_invalid_password():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/token", data={"username": "user@example.com", "password": "wrongpassword"})
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]

@pytest.mark.asyncio
async def test_access_protected_route_without_token():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/users/me/")
        assert response.status_code == 401
        assert "Could not validate credentials" in response.json()["detail"]

@pytest.mark.asyncio
async def test_create_and_retrieve_contact():
    token = "your_valid_token_here"
    contact_data = {"name": "John Doe", "email": "johndoe@example.com", "phone": "1234567890"}
    async with AsyncClient(app=app, base_url="http://test") as ac:
        create_response = await ac.post("/contacts/", headers={"Authorization": f"Bearer {token}"}, json=contact_data)
        assert create_response.status_code == 201
        contact_id = create_response.json()["id"]

        get_response = await ac.get(f"/contacts/{contact_id}", headers={"Authorization": f"Bearer {token}"})
        assert get_response.status_code == 200
        assert get_response.json() == contact_data

@pytest.mark.asyncio
async def test_update_contact():
    token = "your_valid_token_here"
    contact_data = {"name": "John New", "email": "johnnew@example.com", "phone": "9876543210"}
    async with AsyncClient(app=app, base_url="http://test") as ac:
        update_response = await ac.put("/contacts/1", headers={"Authorization": f"Bearer {token}"}, json=contact_data)
        assert update_response.status_code == 200
        assert update_response.json()["name"] == "John New"

@pytest.mark.asyncio
async def test_delete_contact():
    token = "your_valid_token_here"
    async with AsyncClient(app=app, base_url="http://test") as ac:
        delete_response = await ac.delete("/contacts/1", headers={"Authorization": f"Bearer {token}"})
        assert delete_response.status_code == 204
        get_response = await ac.get("/contacts/1", headers={"Authorization": f"Bearer {token}"})
        assert get_response.status_code == 404
