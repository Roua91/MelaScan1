import pytest
import random
import string
from werkzeug.security import generate_password_hash, check_password_hash
from unittest.mock import MagicMock

# Mock Password Service Class
class MockPasswordService:
    @staticmethod
    def generate_permanent_password(length=12, testing=False):
        if testing:
            return "PermanentPass123!"  # Return a fixed password for testing
        
        chars = string.ascii_letters + string.digits + '!@#$%^&*'
        while True:
            password = ''.join(random.choice(chars) for _ in range(length))
            if (any(c.isupper() for c in password) and 
               any(c.islower() for c in password) and 
               any(c.isdigit() for c in password) and 
               any(c in '!@#$%^&*' for c in password)):
                return password

    @staticmethod
    def generate_temp_password(length=10):
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(length))


# Mock User Class with Password Handling
class MockUser:
    def __init__(self):
        self.password_hash = None

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# Test Class for Password Service
class TestMockPasswordService:
    def test_generate_permanent_password_default(self):
        password = MockPasswordService.generate_permanent_password()
        assert len(password) == 12
        assert any(c.isupper() for c in password)
        assert any(c.islower() for c in password)
        assert any(c.isdigit() for c in password)
        assert any(c in '!@#$%^&*' for c in password)

    def test_generate_permanent_password_testing(self):
        password = MockPasswordService.generate_permanent_password(testing=True)
        assert password == "PermanentPass123!"

    def test_generate_temp_password(self):
        password = MockPasswordService.generate_temp_password()
        assert len(password) == 10
        assert password.isalnum()


# Test Class for User Password Handling (Hashing and Checking)
class TestMockUserPassword:
    @pytest.fixture
    def user(self):
        return MockUser()

    def test_set_password(self, user):
        """Test setting and hashing a user's password."""
        user.set_password("Test123!")
        assert user.password_hash is not None
        # Check for either pbkdf2 or scrypt hash format
        assert any(user.password_hash.startswith(prefix) 
               for prefix in ['pbkdf2:sha256:', 'scrypt:'])

    def test_check_password(self, user):
        """Test checking if password matches the hash."""
        user.set_password("Test123!")
        assert user.check_password("Test123!") is True
        assert user.check_password("Wrong!") is False


# Test Class for Password Security (Hash Verification)
class TestPasswordSecurity:
    def test_hash_verification(self):
        """Test if the password hash verification works correctly."""
        password = "SecurePass123!"
        hashed = generate_password_hash(password)
        assert check_password_hash(hashed, password) is True
        assert check_password_hash(hashed, "WrongPass") is False

    def test_hash_uniqueness(self):
        """Test if two hashes of the same password are unique."""
        password = "SamePassword123"
        assert generate_password_hash(password) != generate_password_hash(password)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
