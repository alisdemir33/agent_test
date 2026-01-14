from fastmcp import FastMCP
import oracledb
import json
from datetime import datetime

# MCP Sunucusunu oluştur
mcp = FastMCP("Musteri_Hizmetleri_Yetenekleri")

# Oracle Yapılandırması
DB_CONFIG = {
    "user": "yztest",
    "password": "yztest",
    "dsn": "localhost:1521/DBAI"
}

# --- TOOL 1: Müşteri Doğrulama ---
@mcp.tool()
def verify_customer(name: str, pin: str) -> str:
    """Verifies a customer's identity using their full name and PIN."""
    try:
        conn = oracledb.connect(**DB_CONFIG)
        cursor = conn.cursor()
        parts = name.lower().split()
        first_name, last_name = parts[0], parts[1] if len(parts) > 1 else ""
        
        sql = "SELECT id FROM customers WHERE LOWER(first_name) = :1 AND LOWER(last_name) = :2 AND pin = :3"
        cursor.execute(sql, (first_name, last_name, pin))
        result = cursor.fetchone()
        conn.close()
        return str(result[0]) if result else "-1"
    except Exception as e:
        return f"Error: {e}"

# --- TOOL 2: Siparişleri Getir ---
@mcp.tool()
def get_orders(customer_id: int) -> str:
    """Retrieves the order history for a verified customer."""
    try:
        conn = oracledb.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT id, order_date, product_name, amount FROM orders WHERE customer_id = :1", (customer_id,))
        columns = [col[0] for col in cursor.description]
        orders = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return json.dumps(orders, default=str)
    except Exception as e:
        return f"Error: {e}"

# --- TOOL 3: İade Uygunluk Kontrolü (Business Logic) ---
@mcp.tool()
def check_refund_eligibility(customer_id: int, order_id: int) -> str:
    """Checks if an order is eligible for a refund (30 days rule)."""
    try:
        conn = oracledb.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT order_date FROM orders WHERE id = :1 AND customer_id = :2", (order_id, customer_id))
        result = cursor.fetchone()
        conn.close()
        
        if not result: return "False"
        
        order_date = result[0]
        is_eligible = (datetime.now() - order_date).days <= 30
        return str(is_eligible)
    except Exception as e:
        return f"Error: {e}"
    
@mcp.resource("rag://mevzuat{topic}")
def get_mevzuat_rag(topic: str = "genel") -> str:
    """
    Milvus ve MinIO üzerinden ilgili mevzuat parçalarını bulur ve döner.
    Model bu kaynağı 'bilgi edinmek' için okur.
    """
    # TEMSİLİ RAG AKIŞI:
    # 1. query'yi embedding'e çevir.
    # 2. Milvus'ta benzerlik araması yap.
    # 3. En yakın 3 döküman parçasını birleştir.
    
   # print(f"RAG Sistemi '{topic}' için arama yapıyor...")
    
    rag_sonucu = """
    [Döküman 1]: İşsizlik ödeneği ödemeleri her ayın 5'inde yapılır.
    [Döküman 2]: Ödemeler PTT şubelerinden veya banka hesabından alınabilir.
    """
    return f"{topic} hakkında RAG içeriği"+rag_sonucu

if __name__ == "__main__":
    mcp.run()