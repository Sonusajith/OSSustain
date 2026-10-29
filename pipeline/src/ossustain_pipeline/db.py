"""PostgreSQL connection helper. Schema changes remain owned by Flyway."""

import psycopg

from ossustain_pipeline.config import PipelineConfig


def connect(config: PipelineConfig) -> psycopg.Connection:
    """Open a connection using the validated database URL."""
    return psycopg.connect(str(config.database_url))
