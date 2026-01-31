"""
Helper functions for authentication in integration tests.

Provides utility functions to create users, login, and manage authentication cookies.
"""

from httpx import AsyncClient


async def create_and_login_user(
    client: AsyncClient,
    email: str,
    password: str,
    first_name: str = "Test",
    last_name: str = "User",
    is_admin: bool = False,
    return_cookies_only: bool = False,
):
    """
    Creates a new user and logs them in.

    Args:
        client: HTTP client for making requests
        email: User email
        password: User password
        first_name: User first name
        last_name: User last name
        is_admin: Whether the user should be admin (requires manual DB update)
        return_cookies_only: If True, only returns cookies (assumes user exists)

    Returns:
        tuple: (user_data, cookies) or just cookies if return_cookies_only=True
    """
    if not return_cookies_only:
        # Register user
        register_response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "first_name": first_name,
                "last_name": last_name,
            },
        )

        assert register_response.status_code == 201
        user_data = register_response.json()

        # If admin flag is requested, we need to update the user in the database
        # This is a limitation: we can't set is_admin via API (security)
        # For now, we'll skip admin tests or manually update DB in fixture
        if is_admin:
            # TODO: Update user in DB to set is_admin=True
            # This requires direct database access in tests
            pass

    # Login to get cookies
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )

    assert login_response.status_code == 200
    cookies = login_response.cookies

    if return_cookies_only:
        return cookies

    return user_data, cookies
