from abc import ABC, abstractmethod
from typing import Dict, List, Any
import sqlite3
import json

class IResearchStore(ABC):
    @abstractmethod
    def save_alpha(self, alpha_record: Dict[str, Any]):
        pass
        
    @abstractmethod
    def get_alpha(self, alpha_id: str) -> Dict[str, Any]:
        pass
        
    @abstractmethod
    def get_leaderboard(self, metric: str, top_n: int = 100) -> List[Dict[str, Any]]:
        pass

class SQLiteResearchStore(IResearchStore):
    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path)
        self._create_tables()
        
    def _create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS alphas (
                alpha_id TEXT PRIMARY KEY,
                category TEXT,
                sharpe REAL,
                pbo REAL,
                edge_score REAL,
                data TEXT
            )
        """)
        self.conn.commit()
        
    def save_alpha(self, alpha_record: Dict[str, Any]):
        a_id = alpha_record.get('alpha_id')
        cat = alpha_record.get('category', 'Experimental')
        sharpe = alpha_record.get('metrics', {}).get('sharpe', 0.0)
        pbo = alpha_record.get('metrics', {}).get('pbo', 1.0)
        edge = alpha_record.get('edge_score', 0.0)
        
        data_str = json.dumps(alpha_record)
        
        self.conn.execute("""
            INSERT OR REPLACE INTO alphas (alpha_id, category, sharpe, pbo, edge_score, data)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (a_id, cat, sharpe, pbo, edge, data_str))
        self.conn.commit()
        
    def get_alpha(self, alpha_id: str) -> Dict[str, Any]:
        cur = self.conn.execute("SELECT data FROM alphas WHERE alpha_id = ?", (alpha_id,))
        row = cur.fetchone()
        if row:
            return json.loads(row[0])
        return None
        
    def get_leaderboard(self, metric: str, top_n: int = 100) -> List[Dict[str, Any]]:
        # Map metric to column safely
        col = 'edge_score'
        if metric == 'sharpe': col = 'sharpe'
        elif metric == 'pbo': col = 'pbo'
        
        order = "DESC" if col != "pbo" else "ASC"
        
        cur = self.conn.execute(f"SELECT data FROM alphas ORDER BY {col} {order} LIMIT ?", (top_n,))
        return [json.loads(row[0]) for row in cur.fetchall()]

class DuckDBResearchStore(IResearchStore):
    def __init__(self, db_path: str = ":memory:"):
        import duckdb
        self.conn = duckdb.connect(db_path)
        self._create_tables()
        
    def _create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS alphas (
                alpha_id VARCHAR,
                category VARCHAR,
                sharpe DOUBLE,
                pbo DOUBLE,
                edge_score DOUBLE,
                data VARCHAR
            )
        """)
        
    def save_alpha(self, alpha_record: Dict[str, Any]):
        a_id = alpha_record.get('alpha_id')
        cat = alpha_record.get('category', 'Experimental')
        sharpe = alpha_record.get('metrics', {}).get('sharpe', 0.0)
        pbo = alpha_record.get('metrics', {}).get('pbo', 1.0)
        edge = alpha_record.get('edge_score', 0.0)
        
        data_str = json.dumps(alpha_record)
        
        # Simple upsert logic for DuckDB (delete then insert)
        self.conn.execute("DELETE FROM alphas WHERE alpha_id = ?", [a_id])
        self.conn.execute("""
            INSERT INTO alphas (alpha_id, category, sharpe, pbo, edge_score, data)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [a_id, cat, sharpe, pbo, edge, data_str])
        
    def get_alpha(self, alpha_id: str) -> Dict[str, Any]:
        row = self.conn.execute("SELECT data FROM alphas WHERE alpha_id = ?", [alpha_id]).fetchone()
        if row:
            return json.loads(row[0])
        return None
        
    def get_leaderboard(self, metric: str, top_n: int = 100) -> List[Dict[str, Any]]:
        col = 'edge_score'
        if metric == 'sharpe': col = 'sharpe'
        elif metric == 'pbo': col = 'pbo'
        
        order = "DESC" if col != "pbo" else "ASC"
        
        rows = self.conn.execute(f"SELECT data FROM alphas ORDER BY {col} {order} LIMIT ?", [top_n]).fetchall()
        return [json.loads(row[0]) for row in rows]
