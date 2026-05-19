import hashlib


SALT = 'mark'

def encrypt_password(password: str) -> str:
    """
    密码加密（MD5 + 盐值）
    """
    salted_password = password + SALT
    return hashlib.md5(salted_password.encode('utf-8')).hexdigest()
