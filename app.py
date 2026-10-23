# 快递取件通知系统（贯穿全学期 · app.py）
# 说明：原指导书里"app.py 完整代码（点击展开）"是空占位符，没有实际代码。
# 本文件按课程总览规范编写（Flask + Redis，约 180 行），
# 功能 = 登记包裹 + 取件码查询 + 确认取件 + 管理面板统计。
# 实验一仅需 git push；运行/容器化在实验三（Docker）、实验四（K8s）。

from flask import Flask, request, render_template_string
import redis
import random
import string
import datetime

app = Flask(__name__)

# Redis 连接。实验一单机直接连 localhost；
# 实验三会把 redis 放到 docker-compose 同网络下。
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)


def gen_code() -> str:
    """生成形如 3C-A4F8 的取件码：2 位 + 连字符 + 4 位，大写字母+数字。"""
    alpha = string.ascii_uppercase + string.digits
    return ''.join(random.choices(alpha, k=2)) + '-' + ''.join(random.choices(alpha, k=4))


HOMEPAGE = '''
<!doctype html>
<html><head><meta charset="utf-8"><title>快递取件通知系统</title>
<style>
body{font-family:sans-serif;max-width:760px;margin:24px auto;padding:0 16px;}
h1{color:#1f6feb}
section{border:1px solid #d0d7de;border-radius:8px;padding:16px;margin:12px 0;}
input,button{padding:8px;font-size:14px}
input[type=text]{width:200px}
button{background:#1f6feb;color:#fff;border:none;border-radius:6px;cursor:pointer}
table{width:100%;border-collapse:collapse;margin-top:8px}
th,td{border-bottom:1px solid #eee;padding:6px;text-align:left}
.tag{font-size:12px;padding:2px 8px;border-radius:10px}
.tag-p{background:#fff8c5;color:#735c0f}
.tag-d{background:#dafbe1;color:#1a7f37}
</style></head><body>
<h1>📦 快递取件通知系统</h1>

<section>
  <h3>① 登记包裹（生成取件码）</h3>
  <form action="/add" method="post">
    收件人手机号：<input type="text" name="phone" required>
    <button type="submit">登记</button>
  </form>
</section>

<section>
  <h3>② 手机尾号查询</h3>
  <form action="/query" method="post">
    输入手机号：<input type="text" name="phone" required>
    <button type="submit">查询</button>
  </form>
</section>

<section>
  <h3>③ 凭取件码确认取件</h3>
  <form action="/pickup" method="post">
    取件码：<input type="text" name="code" placeholder="如 3C-A4F8" required>
    <button type="submit">确认取件</button>
  </form>
</section>

<p><a href="/admin">→ 管理面板统计</a></p>
</body></html>
'''


RESULT_TPL = '''
<!doctype html><html><head><meta charset="utf-8"><title>查询结果</title>
<style>body{font-family:sans-serif;max-width:760px;margin:24px auto;padding:0 16px;}
table{width:100%;border-collapse:collapse}
th,td{border-bottom:1px solid #eee;padding:8px;text-align:left}
.tag-p{background:#fff8c5;color:#735c0f;padding:2px 8px;border-radius:10px;font-size:12px}
.tag-d{background:#dafbe1;color:#1a7f37;padding:2px 8px;border-radius:10px;font-size:12px}
a{color:#1f6feb}</style></head><body>
<h3>手机 {{ phone }} 的包裹</h3>
{% if rows %}
<table><tr><th>取件码</th><th>状态</th><th>登记时间</th></tr>
{% for r in rows %}
<tr><td><b>{{ r.code }}</b></td>
<td>{% if r.status=='pending' %}<span class="tag-p">待取</span>{% else %}<span class="tag-d">已取</span>{% endif %}</td>
<td>{{ r.time }}</td></tr>
{% endfor %}
</table>
{% else %}
<p>暂无包裹。</p>
{% endif %}
<p><a href="/">← 返回首页</a></p>
</body></html>
'''


ADMIN_TPL = '''
<!doctype html><html><head><meta charset="utf-8"><title>管理面板</title>
<style>body{font-family:sans-serif;max-width:760px;margin:24px auto;padding:0 16px;}
.card{display:inline-block;border:1px solid #d0d7de;border-radius:8px;padding:16px;margin:6px;min-width:140px;text-align:center}
.num{font-size:32px;color:#1f6feb;font-weight:bold}
table{width:100%;border-collapse:collapse;margin-top:16px}
th,td{border-bottom:1px solid #eee;padding:6px;text-align:left}
.tag-p{background:#fff8c5;color:#735c0f;padding:2px 8px;border-radius:10px;font-size:12px}
.tag-d{background:#dafbe1;color:#1a7f37;padding:2px 8px;border-radius:10px;font-size:12px}
a{color:#1f6feb}</style></head><body>
<h3>📊 管理面板</h3>
<div class="card"><div>总包裹数</div><div class="num">{{ total }}</div></div>
<div class="card"><div>待取</div><div class="num">{{ pending }}</div></div>
<div class="card"><div>已取</div><div class="num">{{ picked }}</div></div>

<table><tr><th>取件码</th><th>手机</th><th>状态</th><th>登记时间</th></tr>
{% for r in rows %}
<tr><td><b>{{ r.code }}</b></td><td>{{ r.phone }}</td>
<td>{% if r.status=='pending' %}<span class="tag-p">待取</span>{% else %}<span class="tag-d">已取</span>{% endif %}</td>
<td>{{ r.time }}</td></tr>
{% endfor %}
</table>
<p><a href="/">← 返回首页</a></p>
</body></html>
'''


@app.route('/')
def home():
    return HOMEPAGE


@app.route('/add', methods=['POST'])
def add():
    phone = request.form['phone'].strip()
    if not phone:
        return '手机号不能为空', 400
    code = gen_code()
    key = f'pkg:{code}'
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    r.hset(key, mapping={
        'phone': phone, 'code': code, 'status': 'pending', 'created': now,
    })
    r.sadd('pkg:all', code)
    return f'登记成功！取件码：<b style="font-size:24px;color:#1f6feb">{code}</b><br><a href="/">返回首页</a>'


@app.route('/query', methods=['POST'])
def query():
    phone = request.form['phone'].strip()
    rows = []
    for code in r.smembers('pkg:all'):
        data = r.hgetall(f'pkg:{code}')
        if data and phone and data.get('phone', '')[-4:] == phone[-4:]:
            rows.append({'code': code, 'status': data.get('status', ''), 'time': data.get('created', '')})
    from jinja2 import Template
    return Template(RESULT_TPL).render(phone=phone, rows=rows)


@app.route('/pickup', methods=['POST'])
def pickup():
    code = request.form['code'].strip().upper()
    key = f'pkg:{code}'
    if not r.exists(key):
        return f'取件码 {code} 不存在', 404
    r.hset(key, 'status', 'picked')
    return f'已确认取件：<b>{code}</b><br><a href="/">返回首页</a>'


@app.route('/admin')
def admin():
    rows = []
    pending = picked = 0
    for code in r.smembers('pkg:all'):
        data = r.hgetall(f'pkg:{code}')
        if data:
            if data.get('status') == 'pending':
                pending += 1
            else:
                picked += 1
            rows.append({'code': code, 'phone': data.get('phone', ''),
                         'status': data.get('status', ''),
                         'time': data.get('created', '')})
    total = pending + picked
    rows.sort(key=lambda x: x['time'], reverse=True)
    from jinja2 import Template
    return Template(ADMIN_TPL).render(total=total, pending=pending, picked=picked, rows=rows)


@app.route('/healthz')
def healthz():
    return 'ok'


if __name__ == '__main__':
    # 0.0.0.0 让 docker/k8s 外部能访问

    app.run(host="0.0.0.0", port=5000)
