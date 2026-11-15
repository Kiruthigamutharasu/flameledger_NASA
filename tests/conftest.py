"""Tests never call Gemini: real environment values are blanked before the app loads .env."""
import os

os.environ["GEMINI_API_KEY"] = ""
os.environ["GEMINI_MODEL"] = ""
