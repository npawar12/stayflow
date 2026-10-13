import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres@localhost:5432/stayflow")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-secret-change-me-in-production-0123456789")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "120"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

# Loyalty program
POINTS_PER_DOLLAR = 10
TIERS = [  # (minimum lifetime points, tier name), highest first
    (50_000, "Platinum"),
    (25_000, "Gold"),
    (10_000, "Silver"),
    (0, "Member"),
]
WEEKEND_MULTIPLIER = 1.2  # Friday and Saturday nights
