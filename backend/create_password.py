import bcrypt

# Create password hash for 'testops123'
password = "testops123"
password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

print(f"Password: {password}")
print(f"Hash: {password_hash.decode('utf-8')}")

# Verify the hash
is_valid = bcrypt.checkpw(password.encode('utf-8'), password_hash)
print(f"Verification: {is_valid}") 