import sqlite3
import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="Thay đổi tên model Local Docker Model Runner (DMR) trong SQLite.")
    parser.add_argument("--type", choices=["embedding", "reranker"], required=True, help="Loại service cần đổi: embedding hoặc reranker")
    parser.add_argument("--model", required=True, help="Tên model mới muốn thiết lập")
    
    args = parser.parse_args()
    
    # DB path trong docker container
    db_path = "/app/data/settings.db"
    
    try:
        db = sqlite3.connect(db_path)
        cur = db.cursor()
        
        # Cập nhật tên model cho provider DMR
        cur.execute(
            "UPDATE ai_providers SET model = ?, updated_at = CURRENT_TIMESTAMP WHERE provider_name = 'dmr' AND service_type = ?",
            (args.model, args.type)
        )
        
        if cur.rowcount == 0:
            print(f"❌ Không tìm thấy cấu hình fallback DMR cho '{args.type}' trong DB.")
            sys.exit(1)
            
        db.commit()
        print(f"✅ Đã cập nhật thành công model cho {args.type} (Local Docker) thành: {args.model}")
        
    except Exception as e:
        print(f"❌ Lỗi khi cập nhật Database: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
