#!/usr/bin/env python3
"""Create or refresh the Firebase account used for MediSkye UI testing."""

import firebase_admin
from firebase_admin import auth as fb_auth


PROJECT_ID = "mediskye-backend"
TEST_EMAIL = "testuser@mediskye.com"
TEST_PASSWORD = "Password123!"


def init_firebase() -> None:
    if not firebase_admin._apps:
        try:
            firebase_admin.initialize_app(options={"projectId": PROJECT_ID})
        except Exception:
            firebase_admin.initialize_app()


def main() -> None:
    init_firebase()

    try:
        user = fb_auth.get_user_by_email(TEST_EMAIL)
    except fb_auth.UserNotFoundError:
        user = fb_auth.create_user(
            email=TEST_EMAIL,
            password=TEST_PASSWORD,
            email_verified=True,
        )
        print(f"Created Firebase user: {user.uid}")
    else:
        user = fb_auth.update_user(
            user.uid,
            password=TEST_PASSWORD,
            email_verified=True,
        )
        print(f"Updated Firebase user: {user.uid}")

    verified_user = fb_auth.get_user(user.uid)
    if verified_user.email != TEST_EMAIL or not verified_user.email_verified:
        raise RuntimeError(
            f"Firebase user is not ready: email={verified_user.email!r}, "
            f"email_verified={verified_user.email_verified}"
        )

    print("Firebase auth readiness check passed: account exists and email is verified.")
    print("\nUse these credentials on the login screen:")
    print(f"Email:    {TEST_EMAIL}")
    print(f"Password: {TEST_PASSWORD}")


if __name__ == "__main__":
    main()
