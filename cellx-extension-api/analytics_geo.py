"""Local, country-level DB-IP lookups. No visitor addresses leave this server."""
import ipaddress
import os
import sqlite3
from functools import lru_cache

GEO_DB = os.getenv("ANALYTICS_GEO_DB", os.path.join(os.path.dirname(__file__), "geo-country.sqlite3"))

@lru_cache(maxsize=8192)
def country_for_ip(value):
    try:
        address = ipaddress.ip_address(str(value or "").strip())
        if getattr(address, "ipv4_mapped", None):
            address = address.ipv4_mapped
        if not address.is_global:
            return ""
        key = format(int(address), "032x")
        with sqlite3.connect("file:" + GEO_DB + "?mode=ro", uri=True) as conn:
            row = conn.execute("SELECT end,country FROM ranges WHERE family=? AND start<=? ORDER BY start DESC LIMIT 1", (address.version,key)).fetchone()
        return row[1] if row and key <= row[0] and len(row[1]) == 2 and row[1] != "ZZ" else ""
    except (ValueError, TypeError, sqlite3.Error, OSError):
        return ""

def country_code(stored, address):
    code = str(stored or "").strip().upper()
    return code if len(code) == 2 and code.isalpha() and code not in {"XX", "ZZ", "T1"} else country_for_ip(address)

def country_summary(conn, cutoff):
    conn.create_function("analytics_country", 2, country_code)
    rows = conn.execute("""SELECT analytics_country(country,ip_address) AS country,
        COUNT(*) AS visits,
        COUNT(DISTINCT CASE WHEN visitor_id != '' THEN visitor_id ELSE ip_address END) AS visitors
        FROM visitor_events WHERE created_at >= ? GROUP BY 1 ORDER BY visits DESC,country""", (cutoff,)).fetchall()
    return [dict(row) for row in rows]

def geo_metadata():
    try:
        with sqlite3.connect("file:"+GEO_DB+"?mode=ro", uri=True) as conn:
            row=conn.execute("SELECT value FROM metadata WHERE key='edition'").fetchone()
        return {"available": True,"source": "DB-IP Lite", "edition": row[0] if row else ""}
    except (sqlite3.Error,OSError):
        return {"available": False,"source": "DB-IP Lite", "edition": ""}
