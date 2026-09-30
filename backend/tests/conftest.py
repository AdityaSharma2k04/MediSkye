import os

# Set test environment variables before modules are loaded
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test_jwt_secret_key_at_least_32_characters_long_for_unit_tests!"
)
