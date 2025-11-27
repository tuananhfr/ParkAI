# Claude Commands cho ParkAI Project

## Slash Commands có sẵn

### `/build-park-system`

Tạo kiến trúc hệ thống + code đầy đủ cho:
- Backend Raspberry Pi + IMX500 camera
- Frontend React real-time streaming + detection
- WebSocket integration
- Hướng dẫn deploy

**Cách dùng:**
```
/build-park-system
```

Claude sẽ output:
✅ Sơ đồ kiến trúc
✅ Code backend đầy đủ (Python FastAPI hoặc Node.js)
✅ Code frontend React đầy đủ
✅ Hướng dẫn deploy lên Raspberry Pi
✅ Tối ưu streaming và accuracy

---

## Cách tạo custom command mới

1. Tạo file `.md` trong `.claude/commands/`
2. Viết prompt theo format markdown
3. Gọi bằng `/tên-file` (không cần .md)

Ví dụ: `.claude/commands/test.md` → gọi bằng `/test`
