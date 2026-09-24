import os
import sqlite3
import json
import structlog
from datetime import datetime

# Calculate Gemini 2.5 Pro pricing approx
def calculate_cost(input_tokens: int, output_tokens: int, thoughts_tokens: int = 0, provider: str = None) -> float:
    if not provider:
        provider = os.environ.get("MODEL_PROVIDER", "gemini").lower()
    else:
        provider = provider.lower()
    
    if provider in ["groq", "mistral", "cerebras"]:
        return 0.0
    return (input_tokens / 1_000_000) * 1.25 + ((output_tokens + thoughts_tokens) / 1_000_000) * 5.00

def setup_logger(instance_id: str):
    os.makedirs("traces", exist_ok=True)
    trace_file = f"traces/{instance_id}.jsonl"
    
    # Configure structlog to write JSON to a specific file
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        logger_factory=structlog.WriteLoggerFactory(file=open(trace_file, "a"))
    )
    return structlog.get_logger()

class Tracer:
    def __init__(self, instance_id: str):
        self.instance_id = instance_id
        self.logger = setup_logger(instance_id)
        self.db_path = "runs.db"
        self._init_db()
        self.start_time = datetime.now()
        self.total_cost = 0.0
        
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS runs (
                    instance_id TEXT PRIMARY KEY,
                    status TEXT,
                    steps_taken INTEGER,
                    total_tokens INTEGER,
                    cost_usd REAL,
                    wall_clock_seconds REAL,
                    timestamp TEXT,
                    thoughts_tokens INTEGER
                )
            ''')
            # Handle schema migration if table existed before
            try:
                cursor.execute('ALTER TABLE runs ADD COLUMN thoughts_tokens INTEGER DEFAULT 0')
            except sqlite3.OperationalError:
                pass
            conn.commit()

    def log_step(self, step_number: int, tool_called: str, tool_result_summary: str, model_input_tokens: int, model_output_tokens: int, latency_ms: float, thoughts_token_count: int = 0, provider_used: str = None):
        """Log an individual agent step to the JSONL trace."""
        step_cost = calculate_cost(model_input_tokens, model_output_tokens, thoughts_token_count, provider_used)
        self.total_cost += step_cost
        
        self.logger.info(
            "agent_step",
            task_id=self.instance_id,
            step_number=step_number,
            tool_called=tool_called,
            tool_result_summary=tool_result_summary,
            model_input_tokens=model_input_tokens,
            model_output_tokens=model_output_tokens,
            thoughts_token_count=thoughts_token_count,
            latency_ms=latency_ms,
            provider_used=provider_used
        )
        
    def record_run(self, status: str, steps_taken: int, total_input_tokens: int, total_output_tokens: int, total_thoughts_tokens: int = 0, provider: str = "unknown"):
        """Save the summary of the task to the SQLite database."""
        end_time = datetime.now()
        wall_clock_seconds = (end_time - self.start_time).total_seconds()
        total_tokens = total_input_tokens + total_output_tokens + total_thoughts_tokens
        timestamp = end_time.isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO runs 
                (instance_id, status, steps_taken, total_tokens, cost_usd, wall_clock_seconds, timestamp, thoughts_tokens, provider) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (self.instance_id, status, steps_taken, total_tokens, self.total_cost, wall_clock_seconds, timestamp, total_thoughts_tokens, provider))
            conn.commit()
