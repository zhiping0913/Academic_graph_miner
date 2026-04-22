"""Backend configuration and paths."""
import os

OUTPUT_PATH = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(OUTPUT_PATH, "academic_knowledge_graph.db")

# Legacy JSON path kept for the migration script
DATA_FILE = "academic_knowledge_graph.json"
DATA_FILE_PATH = os.path.join(OUTPUT_PATH, DATA_FILE)
