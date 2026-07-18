from setuptools import setup, find_packages

setup(
    name="anomaly-on-binance",
    version="0.1.0",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "psycopg[binary]>=3.1",
        "pandas>=2.0",
        "numpy>=1.26",
        "scikit-learn>=1.4",
        "mlflow>=2.12",
        "evidently>=0.4",
        "dagster>=1.7",
        "dagster-webserver>=1.7",
        "prometheus-client>=0.20",
        "streamlit>=1.34",
        "python-dotenv>=1.0",
    ],
    extras_require={
        "dev": ["pytest>=8.0", "ruff>=0.4"],
        "producer": [
            "aiokafka==0.9.0",
            "websockets==11.0.3",
            "pydantic==1.10.11",
            "uvloop==0.17.0",
            "orjson==3.9.1",
        ],
    },
)
