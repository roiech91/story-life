#!/usr/bin/env python3
"""
Generate a secure secret key for JWT token signing.
Run this script to generate a new SECRET_KEY for production.
"""

import secrets

if __name__ == "__main__":
    secret_key = secrets.token_urlsafe(32)
    print(f"\n🔐 Generated SECRET_KEY:")
    print(f"{secret_key}\n")
    print("Copy this value to your environment variables (Railway/Render)")
    print("⚠️  Keep this secret! Don't commit it to version control.\n")

