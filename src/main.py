import logging

from src.api.rest.app import create_app

logging.basicConfig(level=logging.INFO)

app = create_app()

