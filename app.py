"""快递取件通知系统 —— Flask + Redis Web 应用"""
from flask import Flask, request, render_template_string
import redis, hashlib, random, time, os

app = Flask(__name__)
r = redis.Redis(host=os.environ.get('REDIS_HOST', 'localhost'),
                port=6379, decode_responses=True)

BASE_HTML = '''<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>📦 快递取件通知系统</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#f0f2f5;min-height:100vh}}
.nav{{background:#1a1a2e;color:#fff;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.nav h2{{font-size:18px}}.nav a{{color:#94a3b8;text-decoration:none;margin-left:20px;font-size:14px}}
.nav a:hover{{color:#fff}}
.container{{max-width:720px;margin:24px auto;padding:0 16px}}
.card{{background:#fff;border-radius:10px;padding:20px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,0.08)}}
.card h3{{margin-bottom:12px;color:#1a1a2e}}
.search-box{{display:flex;gap:8px}}
.search-box input{{flex:1;padding:10px 14px;border:1px solid #d1d5db;border-radius:8px;font-size:15px}}
.search-box input:focus{{outline:none;border-color:#2563eb;box-shadow:0 0 0 3px rgba(37,99,235,0.1)}}
.btn{{padding:10px 20px;border:none;border-radius:8px;cursor:pointer;font-size:14px;font-weight:500}}
.btn-primary{{background:#2563eb;color:#fff}}.btn-primary:hover{{background:#1d4ed8}}
.btn-success{{background:#10b981;color:#fff}}.btn-success:hover{{background:#059669}}
.btn-sm{{padding:6px 14px;font-size:13px}}
.pkg-card{{display:flex;justify-content:space-between;align-items:center;padding:14px 0;border-bottom:1px solid #f0f0f0}}
.pkg-card:last-child{{border-bottom:none}}
.pkg-info .code{{font-size:20px;font-weight:700;color:#1a1a2e;letter-spacing:1px}}
.pkg-info .meta{{font-size:13px;color:#888;margin-top:4px}}
.pkg-status{{padding:4px 12px;border-radius:20px;font-size:12px;font-weight:500}}
.status-pending{{background:#fef3c7;color:#d97706}}
.status-picked{{background:#d1fae5;color:#059669}}
.stats{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:16px}}
.stat-card{{background:#fff;border-radius:10px;padding:16px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,0.08)}}
.stat-card .num{{font-size:28px;font-weight:700;color:#2563eb}}
.stat-card .label{{font-size:12px;color:#888;margin-top:4px}}
.empty{{text-align:center;padding:40px;color:#999}}
.form-group{{margin-bottom:14px}}
.form-group label{{display:block;margin-bottom:4px;font-size:13px;color:#555;font-weight:500}}
.form-group input,.form-group select{{width:100%;padding:10px 14px;border:1px solid #d1d5db;border-radius:8px;font-size:14px}}
.form-group input:focus{{outline:none;border-color:#2563eb}}
</style></head><body>
<div class="nav"><h2>📦 快递取件通知系统</h2>
<div><a href="/">🔍 查询包裹</a><a href="/register">📝 登记包裹</a><a href="/dashboard">📊 管理面板</a></div></div>
<div class="container">{content}</div></body></html>'''

def gen_code():
    floor = random.randint(1, 5)
    area = random.choice(['A', 'B', 'C', 'D', 'E'])
    suffix = hashlib.md5(str(random.random()).encode()).hexdigest()[:4].upper()
    return f'{floor}{area}-{suffix}'

@app.route('/')
def index():
    content = '''<div class="card"><h3>🔍 查询我的包裹</h3>
    <form action="/query" method="GET" class="search-box">
    <input type="text" name="phone" placeholder="输入手机号后四位，如 8829" pattern="[0-9]{4}" required>
    <button class="btn btn-primary" type="submit">查询</button></form></div>'''
    return BASE_HTML.format(content=content)

@app.route('/query')
def query():
    phone = request.args.get('phone', '').strip()
    if len(phone) != 4 or not phone.isdigit():
        return BASE_HTML.format(content='<div class="card"><p class="empty">请输入4位手机号</p></div>')
    all_keys = r.keys('phone:*')
    matched = [k.split(':')[1] for k in all_keys if k.split(':')[1].endswith(phone)]
    if not matched:
        content = f'<div class="card"><p class="empty">未找到尾号 {phone} 的包裹</p><a href="/" class="btn btn-primary">返回</a></div>'
        return BASE_HTML.format(content=content)
    full_phone = matched[0]
    codes = r.smembers(f'phone:{full_phone}')
    pkgs = [r.hgetall(f'pkg:{c}') | {'code': c} for c in codes]
    pkgs.sort(key=lambda p: p.get('created_at', ''), reverse=True)
    rows = ''
    for p in pkgs:
        status_cls = 'status-pending' if p.get('status') == 'pending' else 'status-picked'
        status_text = '⏳ 待取件' if p.get('status') == 'pending' else '✅ 已取件'
        pickup_btn = ''
        if p.get('status') == 'pending':
            pickup_btn = f'<a href="/pickup/{p["code"]}?phone={phone}" class="btn btn-success btn-sm">确认取件</a>'
        rows += f'''<div class="pkg-card"><div class="pkg-info">
        <div class="code">📦 {p["code"]}</div>
        <div class="meta">{p.get("carrier","")} · {p.get("shelf","")} · {p.get("created_at","")}</div></div>
        <div style="display:flex;align-items:center;gap:10px">
        <span class="pkg-status {status_cls}">{status_text}</span>{pickup_btn}</div></div>'''
    content = f'''<div class="card"><h3>📋 尾号 {phone} 的包裹 ({len(pkgs)}件)</h3>{rows}</div>
    <a href="/" class="btn btn-primary">← 返回</a>'''
    return BASE_HTML.format(content=content)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        phone = request.form.get('phone', '')
        carrier = request.form.get('carrier', '')
        shelf = request.form.get('shelf', '')
        code = gen_code()
        r.hset(f'pkg:{code}', mapping={
            'phone': phone, 'carrier': carrier, 'shelf': shelf,
            'status': 'pending',
            'created_at': time.strftime('%Y-%m-%d %H:%M')
        })
        r.sadd(f'phone:{phone}', code)
        r.zadd('packages:pending', {code: time.time()})
        content = f'''<div class="card" style="text-align:center"><h3>✅ 包裹登记成功</h3>
        <div class="code" style="font-size:32px;margin:16px 0">{code}</div>
        <p style="color:#888">快递公司: {carrier} · 货架: {shelf} · 手机尾号: {phone[-4:]}</p>
        <a href="/register" class="btn btn-primary" style="margin-top:12px">继续登记</a>
        <a href="/dashboard" class="btn btn-primary" style="margin-top:12px">查看面板</a></div>'''
        return BASE_HTML.format(content=content)
    form = '''<div class="card"><h3>📝 登记新包裹</h3>
    <form method="POST">
    <div class="form-group"><label>收件人手机号</label>
    <input type="text" name="phone" placeholder="如 13888888829" required></div>
    <div class="form-group"><label>快递公司</label>
    <select name="carrier"><option>中通快递</option><option>圆通速递</option>
    <option>顺丰速运</option><option>申通快递</option><option>韵达快递</option>
    <option>京东物流</option><option>极兔速递</option><option>邮政EMS</option></select></div>
    <div class="form-group"><label>货架位置</label>
    <input type="text" name="shelf" placeholder="如 C区-3层" required></div>
    <button class="btn btn-primary" type="submit">确认登记</button></form></div>'''
    return BASE_HTML.format(content=form)

@app.route('/pickup/<code>')
def pickup(code):
    pkg = r.hgetall(f'pkg:{code}')
    if not pkg:
        return BASE_HTML.format(content='<div class="card"><p class="empty">包裹不存在</p></div>')
    r.hset(f'pkg:{code}', 'status', 'picked')
    r.hset(f'pkg:{code}', 'picked_at', time.strftime('%Y-%m-%d %H:%M'))
    r.zrem('packages:pending', code)
    r.zadd('packages:picked', {code: time.time()})
    content = f'''<div class="card" style="text-align:center"><h3>✅ 取件成功</h3>
    <p style="margin:12px 0">包裹 {code} 已标记为已取件</p>
    <p style="color:#888">{pkg.get("carrier")} · {pkg.get("shelf")}</p>
    <a href="/dashboard" class="btn btn-primary" style="margin-top:12px">查看面板</a></div>'''
    return BASE_HTML.format(content=content)

@app.route('/dashboard')
def dashboard():
    pending_count = r.zcard('packages:pending')
    picked_today = sum(1 for c in r.zrange('packages:picked', 0, -1))
    total_count = len(r.keys('pkg:*'))
    pending = r.zrange('packages:pending', 0, -1, withscores=True)
    rows = ''
    for code, ts in pending:
        p = r.hgetall(f'pkg:{code}')
        if p:
            rows += f'''<div class="pkg-card"><div class="pkg-info">
            <div class="code">📦 {code}</div>
            <div class="meta">{p.get("carrier","")} · {p.get("shelf","")} · 尾号{p.get("phone","")[-4:]} · {p.get("created_at","")}</div></div>
            <a href="/pickup/{code}" class="btn btn-success btn-sm">确认取件</a></div>'''
    content = f'''<div class="stats"><div class="stat-card"><div class="num">{pending_count}</div><div class="label">待取件</div></div>
    <div class="stat-card"><div class="num">{picked_today}</div><div class="label">已取件</div></div>
    <div class="stat-card"><div class="num">{total_count}</div><div class="label">总包裹数</div></div></div>
    <div class="card"><h3>📦 待取件包裹列表</h3>{rows or '<p class="empty">暂无待取包裹</p>'}</div>
    <a href="/register" class="btn btn-primary">登记新包裹</a>'''
    return BASE_HTML.format(content=content)

@app.route('/health')
def health():
    r.ping()
    return "OK", 200

if __name__ == '__main__':
<<<<<<< HEAD
    # 0.0.0.0 让 docker/k8s 外部能访问

    app.run(host="0.0.0.0", port=5000)
=======
    app.run(host='0.0.0.0', port=5000)
>>>>>>> 0315597 (fix app.py v2)
