from setuptools import setup, find_packages

setup(
    name="fastapi-project",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "flask",
        "uvicorn",
        "requests",
        "python-dotenv",
        "supabase",
        "sqlalchemy",
    ],
)