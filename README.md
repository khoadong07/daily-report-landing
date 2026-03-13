# Daily Report Manager

Web application để tạo và quản lý landing pages từ HTML.

## Tính năng

- ✨ UI đơn giản để paste HTML
- 💾 Tự động save và tạo file
- 🔗 Tạo link truy cập ngay lập tức
- 📁 Quản lý danh sách reports
- 📋 Copy link nhanh chóng

## Cách chạy

### Sử dụng Docker Compose (khuyến nghị):
```bash
docker-compose up -d
```

### Hoặc sử dụng Docker trực tiếp:
```bash
# Build image
docker build -t daily-report .

# Run container
docker run -d -p 8000:8000 -v $(pwd)/reports:/app/reports --name daily-report daily-report
```

### Hoặc chạy trực tiếp với Python:
```bash
pip install -r requirements.txt
python app.py
```

## Truy cập

Mở trình duyệt và truy cập: http://localhost:8000/

## Sử dụng

1. Nhập tên report (vd: nganh-xang-dau)
2. Paste HTML content vào textarea
3. Click "Save & Create Landing Page"
4. Copy link và chia sẻ!

## Dừng container

```bash
# Nếu dùng docker-compose
docker-compose down

# Nếu dùng docker trực tiếp
docker stop daily-report
docker rm daily-report
```
