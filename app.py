"""
OHSS 高蛋白饮食智能计算器 v2.0
- Flask 后端 + SQLite 数据持久化
- 账号认证体系（护士登录）
- 患者信息保存与查询
- 五餐食谱生成 + PDF 报告 + 二维码（在线显示）
"""

from flask import Flask, request, jsonify, send_file, render_template_string, session, redirect, url_for
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
import qrcode
import os
import json
import math
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# ============================================================
# 数据库初始化
# ============================================================
DATABASE = os.environ.get('DB_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ohss.db'))

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT DEFAULT 'nurse',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER,
            height REAL NOT NULL,
            weight REAL NOT NULL,
            gender TEXT DEFAULT 'female',
            waist REAL,
            calf REAL,
            eval_stage TEXT,
            bmi REAL,
            bmi_category TEXT,
            calc_weight REAL,
            calc_weight_method TEXT,
            protein_low REAL,
            protein_high REAL,
            liquid_total REAL,
            actual_drink REAL,
            risk_score INTEGER,
            risk_level TEXT,
            protein_coeff TEXT,
            meal_plan_json TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_patients_name ON patients(name);
        CREATE INDEX IF NOT EXISTS idx_patients_created_at ON patients(created_at DESC);
    ''')

    # 创建默认管理员账号
    cursor = conn.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        default_password = hash_password('ohss2024')
        conn.execute(
            "INSERT INTO users (username, password_hash, display_name, role) VALUES (?, ?, ?, ?)",
            ('admin', default_password, '管理员', 'admin')
        )
        conn.commit()
    conn.close()

def hash_password(password):
    salt = secrets.token_hex(16)
    h = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${h}"

def verify_password(password, stored):
    salt, h = stored.split('$')
    return hashlib.sha256((password + salt).encode()).hexdigest() == h

# 登录验证装饰器
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': '未登录', 'redirect': '/login'}), 401
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated

# ============================================================
# 字体注册
# ============================================================
FONT_NAME = 'MSYH'
FONT_PATH_WIN = 'C:/Windows/Fonts/msyh.ttc'
FONT_PATH_ALT = '/usr/share/fonts/truetype/msyh.ttc'
FONT_PATH_NOTO = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'

def register_font():
    for path in [FONT_PATH_WIN, FONT_PATH_ALT, FONT_PATH_NOTO]:
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont(FONT_NAME, path))
            return True
    return False

FONT_AVAILABLE = register_font()
FONT_FALLBACK = FONT_NAME if FONT_AVAILABLE else 'Helvetica'

# ============================================================
# 食物数据库
# ============================================================
FOOD_DATABASE = [
    {"name": "鸡蛋（中等全蛋）", "portion": "1个(50g)", "protein": 6.5, "water": 35, "category": "蛋类", "unit_g": 50},
    {"name": "鸡蛋白（蛋清）", "portion": "1个蛋清(30g)", "protein": 3.8, "water": 28, "category": "蛋类", "unit_g": 30},
    {"name": "鹌鹑蛋", "portion": "5个(50g)", "protein": 6.5, "water": 35, "category": "蛋类", "unit_g": 50},
    {"name": "纯牛奶", "portion": "250ml/盒", "protein": 8, "water": 220, "category": "奶制品", "unit_g": 250},
    {"name": "无糖酸奶", "portion": "200g/杯", "protein": 7.5, "water": 170, "category": "奶制品", "unit_g": 200},
    {"name": "脱脂奶粉", "portion": "20g", "protein": 7, "water": 1, "category": "奶制品", "unit_g": 20},
    {"name": "奶酪（芝士）", "portion": "30g", "protein": 7.5, "water": 10, "category": "奶制品", "unit_g": 30},
    {"name": "熟鸡胸肉（去皮）", "portion": "100g", "protein": 27.5, "water": 65, "category": "肉类", "unit_g": 100},
    {"name": "熟鸡腿肉（去皮）", "portion": "100g", "protein": 25, "water": 67, "category": "肉类", "unit_g": 100},
    {"name": "熟瘦牛里脊", "portion": "100g", "protein": 22, "water": 60, "category": "肉类", "unit_g": 100},
    {"name": "熟瘦猪肉", "portion": "100g", "protein": 21, "water": 58, "category": "肉类", "unit_g": 100},
    {"name": "熟牛排", "portion": "100g", "protein": 27, "water": 55, "category": "肉类", "unit_g": 100},
    {"name": "熟鸭肉（去皮）", "portion": "100g", "protein": 19, "water": 63, "category": "肉类", "unit_g": 100},
    {"name": "午餐肉/火腿肠", "portion": "100g", "protein": 13, "water": 55, "category": "肉类", "unit_g": 100},
    {"name": "熟虾仁", "portion": "100g", "protein": 18, "water": 75, "category": "水产", "unit_g": 100},
    {"name": "熟鲈鱼/草鱼鱼肉", "portion": "100g", "protein": 17.5, "water": 70, "category": "水产", "unit_g": 100},
    {"name": "熟三文鱼", "portion": "100g", "protein": 22, "water": 64, "category": "水产", "unit_g": 100},
    {"name": "熟带鱼", "portion": "100g", "protein": 18, "water": 70, "category": "水产", "unit_g": 100},
    {"name": "熟鳕鱼", "portion": "100g", "protein": 20, "water": 72, "category": "水产", "unit_g": 100},
    {"name": "北豆腐（老豆腐）", "portion": "100g", "protein": 12, "water": 80, "category": "豆制品", "unit_g": 100},
    {"name": "南豆腐（嫩豆腐）", "portion": "100g", "protein": 6.5, "water": 90, "category": "豆制品", "unit_g": 100},
    {"name": "豆腐干", "portion": "100g", "protein": 25, "water": 55, "category": "豆制品", "unit_g": 100},
    {"name": "豆浆（无糖）", "portion": "250ml", "protein": 6.5, "water": 230, "category": "豆制品", "unit_g": 250},
    {"name": "腐竹（干）", "portion": "20g", "protein": 9.5, "water": 1, "category": "豆制品", "unit_g": 20},
    {"name": "毛豆（鲜）", "portion": "100g", "protein": 13, "water": 70, "category": "豆制品", "unit_g": 100},
    {"name": "米饭（熟）", "portion": "一碗(200g)", "protein": 5.5, "water": 160, "category": "主食", "unit_g": 200},
    {"name": "面条（熟）", "portion": "一碗(200g)", "protein": 5.5, "water": 140, "category": "主食", "unit_g": 200},
    {"name": "馒头", "portion": "1个(100g)", "protein": 7.5, "water": 40, "category": "主食", "unit_g": 100},
    {"name": "全麦面包", "portion": "2片(70g)", "protein": 6.5, "water": 20, "category": "主食", "unit_g": 70},
    {"name": "燕麦片（干）", "portion": "40g", "protein": 5.5, "water": 2, "category": "主食", "unit_g": 40},
    {"name": "小米粥", "portion": "一碗(300ml)", "protein": 3.5, "water": 270, "category": "主食", "unit_g": 300},
    {"name": "白米粥", "portion": "一碗(300ml)", "protein": 2.5, "water": 280, "category": "主食", "unit_g": 300},
    {"name": "西蓝花（熟）", "portion": "100g", "protein": 3.5, "water": 85, "category": "蔬菜", "unit_g": 100},
    {"name": "菠菜（熟）", "portion": "100g", "protein": 3, "water": 88, "category": "蔬菜", "unit_g": 100},
    {"name": "番茄", "portion": "1个(150g)", "protein": 1.3, "water": 140, "category": "蔬菜", "unit_g": 150},
    {"name": "黄瓜", "portion": "100g", "protein": 0.8, "water": 95, "category": "蔬菜", "unit_g": 100},
    {"name": "冬瓜（熟）", "portion": "100g", "protein": 0.5, "water": 95, "category": "蔬菜", "unit_g": 100},
    {"name": "苹果", "portion": "1个(200g)", "protein": 0.5, "water": 150, "category": "水果", "unit_g": 200},
    {"name": "橙子", "portion": "1个(150g)", "protein": 1, "water": 120, "category": "水果", "unit_g": 150},
    {"name": "西瓜", "portion": "200g", "protein": 0.6, "water": 180, "category": "水果", "unit_g": 200},
    {"name": "香蕉", "portion": "1根(100g)", "protein": 1.2, "water": 75, "category": "水果", "unit_g": 100},
    {"name": "乳清蛋白粉", "portion": "1勺(20g粉)", "protein": 17, "water": 1, "category": "营养补充剂", "unit_g": 20},
]

DEDUCTION_ORDER = ["营养补充剂", "豆制品", "奶制品"]

# ============================================================
# 核心计算逻辑
# ============================================================

def calc_bmi(weight_kg, height_cm):
    height_m = height_cm / 100.0
    return round(weight_kg / (height_m ** 2), 1)

def bmi_category(bmi):
    if bmi < 18.5: return "消瘦"
    elif bmi < 24: return "正常"
    elif bmi < 28: return "超重"
    else: return "肥胖"

def calc_ibw(height_cm):
    return height_cm - 105

def calc_adjusted_weight(actual_weight, ibw):
    excess = actual_weight - ibw
    if excess <= 0: return ibw
    return round(ibw + 0.25 * excess, 1)

def determine_calc_weight(actual_weight, height_cm, waist_cm, calf_cm, gender):
    bmi = calc_bmi(actual_weight, height_cm)
    ibw = calc_ibw(height_cm)
    if bmi < 24: return actual_weight, "实际体重"
    waist_threshold = 85 if gender == 'female' else 90
    calf_threshold = 33 if gender == 'female' else 34
    has_waist = waist_cm is not None and waist_cm > 0
    has_calf = calf_cm is not None and calf_cm > 0
    if has_calf and calf_cm < calf_threshold: return actual_weight, "肌少型肥胖→实际体重"
    if has_waist and waist_cm >= waist_threshold: return ibw, "向心性肥胖→理想体重"
    if has_waist and waist_cm < waist_threshold: return calc_adjusted_weight(actual_weight, ibw), "周围型肥胖→校正体重"
    if has_calf: return ibw, "默认理想体重（未测量腰围）"
    return ibw, "默认理想体重（未测量腰围/小腿围）"

def calc_risk_score(assessment_data):
    score = 0
    base_factors = ['pcos', 'prev_ohss', 'age_under_35', 'bmi_under_18_5', 'amh_high', 'afc_high']
    for key in base_factors:
        if assessment_data.get(key): score += 1
    clinical_factors = ['e2_high', 'follicle_high', 'oocyte_high', 'symptoms', 'ovary_enlarged', 'ascites', 'pleural_effusion']
    for key in clinical_factors:
        if assessment_data.get(key): score += 3
    return score

def risk_level(score):
    if score == 0: return "健康饮食级", (1.0, 1.2)
    elif score <= 4: return "预防级", (1.2, 1.5)
    elif score <= 10: return "干预级", (1.5, 1.8)
    else: return "治疗级", (1.8, 2.0)

def calc_protein_range(calc_weight, protein_coeff):
    low, high = protein_coeff
    return round(calc_weight * low, 1), round(calc_weight * high, 1)

def calc_liquid_total(calc_weight):
    return round(calc_weight * 30)

def calc_actual_drink(liquid_total, food_water_total):
    return max(0, liquid_total - food_water_total)

# ============================================================
# 食谱生成
# ============================================================
MEAL_STRUCTURE = {
    "早餐": {"categories": ["蛋类", "奶制品", "主食"], "protein_ratio": 0.25, "max_items": 4, "description": "早餐（7:00-8:00）"},
    "早加餐": {"categories": ["水果", "奶制品", "蛋类"], "protein_ratio": 0.10, "max_items": 2, "description": "早加餐（10:00）"},
    "午餐": {"categories": ["肉类", "水产", "蔬菜", "主食", "豆制品"], "protein_ratio": 0.30, "max_items": 5, "description": "午餐（12:00-13:00）"},
    "午加餐": {"categories": ["水果", "奶制品", "豆制品", "主食"], "protein_ratio": 0.10, "max_items": 2, "description": "午加餐（15:00-16:00）"},
    "晚餐": {"categories": ["肉类", "水产", "蔬菜", "主食", "豆制品", "蛋类"], "protein_ratio": 0.25, "max_items": 5, "description": "晚餐（18:00-19:00）"},
}

def generate_meal_plan(target_protein_high, liquid_total, calc_weight):
    meals = {}
    total_protein = 0
    total_water = 0
    protein_budget = target_protein_high * 0.9
    for meal_name, config in MEAL_STRUCTURE.items():
        meal_target = protein_budget * config["protein_ratio"]
        meal_items = []
        meal_protein = 0
        meal_water = 0
        available = [f for f in FOOD_DATABASE if f["category"] in config["categories"]]
        for _ in range(config["max_items"]):
            if meal_protein >= meal_target: break
            existing_names = {item["name"] for item in meal_items}
            candidates = sorted(
                [f for f in available if f["name"] not in existing_names],
                key=lambda x: x["protein"] / max(x["unit_g"], 1), reverse=True
            )
            if not candidates: break
            best = candidates[0]
            qty = 1
            if meal_protein + best["protein"] > meal_target * 1.2:
                smaller = [c for c in candidates if meal_protein + c["protein"] <= meal_target * 1.2]
                if smaller: best = smaller[0]
                else: break
            item = {"name": best["name"], "portion": best["portion"], "quantity": qty, "protein": best["protein"], "water": best["water"], "category": best["category"]}
            meal_items.append(item)
            meal_protein += best["protein"]
            meal_water += best["water"]
        meals[meal_name] = {"label": config["description"], "items": meal_items, "protein_subtotal": round(meal_protein, 1), "water_subtotal": meal_water}
        total_protein += meal_protein
        total_water += meal_water
    total_protein = round(total_protein, 1)
    if total_protein > target_protein_high:
        excess = total_protein - target_protein_high
        total_protein, total_water, meals = _apply_protein_lock(meals, excess, total_protein, total_water)
    liquid_total_int = round(liquid_total)
    return {"meals": meals, "total_protein": round(total_protein, 1), "total_food_water": total_water, "liquid_total": liquid_total_int, "actual_drink": max(0, liquid_total_int - total_water), "protein_target_high": target_protein_high}

def _apply_protein_lock(meals, excess, total_protein, total_water):
    for category in DEDUCTION_ORDER:
        if excess <= 0: break
        for meal_name in meals:
            if excess <= 0: break
            meal = meals[meal_name]
            for item in list(meal["items"]):
                if excess <= 0: break
                if item["category"] == category:
                    meals[meal_name]["items"].remove(item)
                    meals[meal_name]["protein_subtotal"] = round(meals[meal_name]["protein_subtotal"] - item["protein"], 1)
                    meals[meal_name]["water_subtotal"] -= item["water"]
                    total_protein = round(total_protein - item["protein"], 1)
                    total_water -= item["water"]
                    excess -= item["protein"]
    return total_protein, total_water, meals

# ============================================================
# HTML 模板
# ============================================================
HTML_TEMPLATE = r'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
<meta name="format-detection" content="telephone=no">
<title>OHSS 高蛋白饮食智能计算器</title>
<style>
    :root {
        --primary: #2B5797; --primary-light: #4472C4; --success: #2E7D32;
        --warning: #E65100; --danger: #C62828; --bg: #F5F7FA;
        --card-bg: #FFFFFF; --text: #212121; --text-secondary: #616161;
        --border: #E0E0E0; --radius: 10px; --shadow: 0 2px 8px rgba(0,0,0,0.08);
        --font: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", "Helvetica Neue", sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
        font-family: var(--font); background: var(--bg); color: var(--text);
        font-size: 15px; line-height: 1.5;
        -webkit-text-size-adjust: 100%; -webkit-tap-highlight-color: transparent;
    }
    .container { max-width: 480px; margin: 0 auto; padding: 12px; }
    .header {
        background: linear-gradient(135deg, var(--primary), var(--primary-light));
        color: #fff; padding: 16px 20px; border-radius: var(--radius);
        margin-bottom: 12px; text-align: center;
    }
    .header h1 { font-size: 18px; font-weight: 600; }
    .header .subtitle { font-size: 12px; opacity: 0.85; margin-top: 4px; }
    .header .user-bar {
        display: flex; justify-content: space-between; align-items: center;
        margin-top: 10px; font-size: 12px; opacity: 0.9;
    }
    .header .user-bar a { color: #fff; text-decoration: none; padding: 2px 8px; border: 1px solid rgba(255,255,255,0.4); border-radius: 12px; font-size: 11px; }
    .card { background: var(--card-bg); border-radius: var(--radius); padding: 16px; margin-bottom: 12px; box-shadow: var(--shadow); }
    .card-title { font-size: 16px; font-weight: 600; color: var(--primary); margin-bottom: 12px; padding-bottom: 8px; border-bottom: 2px solid var(--primary-light); display: flex; align-items: center; gap: 6px; }
    .form-row { display: flex; gap: 10px; margin-bottom: 10px; }
    .form-group { flex: 1; margin-bottom: 10px; }
    .form-group label { display: block; font-size: 13px; color: var(--text-secondary); margin-bottom: 4px; font-weight: 500; }
    .form-group input, .form-group select { width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 16px; font-family: var(--font); transition: border-color 0.2s; background: #FAFAFA; -webkit-appearance: none; }
    .form-group input:focus, .form-group select:focus { outline: none; border-color: var(--primary-light); background: #fff; box-shadow: 0 0 0 3px rgba(68,114,196,0.1); }
    .form-hint { font-size: 11px; color: #999; margin-top: 2px; }
    .form-section-title { font-size: 13px; font-weight: 600; color: var(--text-secondary); margin: 12px 0 8px; padding: 6px 10px; background: #F0F4FA; border-radius: 6px; }
    .btn { display: inline-block; padding: 12px 24px; border: none; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; transition: all 0.2s; font-family: var(--font); text-align: center; width: 100%; -webkit-appearance: none; }
    .btn:active { transform: scale(0.97); }
    .btn-primary { background: linear-gradient(135deg, var(--primary), var(--primary-light)); color: #fff; box-shadow: 0 2px 8px rgba(43,87,151,0.3); }
    .btn-outline { background: #fff; color: var(--primary); border: 1.5px solid var(--primary); }
    .btn-sm { padding: 8px 16px; font-size: 13px; width: auto; }
    .btn-xs { padding: 4px 10px; font-size: 11px; width: auto; }
    .btn-danger { background: #fff; color: var(--danger); border: 1.5px solid var(--danger); }
    .btn-row { display: flex; gap: 10px; margin-top: 8px; }
    .btn-row .btn { flex: 1; }
    .result-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .result-item { background: #F5F7FA; padding: 10px; border-radius: 8px; text-align: center; }
    .result-item .label { font-size: 11px; color: var(--text-secondary); margin-bottom: 2px; }
    .result-item .value { font-size: 18px; font-weight: 700; color: var(--primary); }
    .result-item .value-sm { font-size: 14px; font-weight: 600; color: var(--primary); }
    .risk-badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 600; }
    .risk-prevention { background: #E8F5E9; color: #2E7D32; }
    .risk-intervention { background: #FFF3E0; color: #E65100; }
    .risk-treatment { background: #FFEBEE; color: #C62828; }
    .risk-healthy { background: #E3F2FD; color: #1565C0; }
    .meal-section { margin-bottom: 12px; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
    .meal-header { background: #F0F4FA; padding: 10px 14px; font-weight: 600; font-size: 14px; color: var(--primary); display: flex; justify-content: space-between; align-items: center; }
    .meal-header .meal-time { font-size: 12px; color: var(--text-secondary); font-weight: 400; }
    .meal-items { padding: 8px 14px; }
    .meal-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #F5F5F5; font-size: 13px; }
    .meal-item:last-child { border-bottom: none; }
    .meal-item .food-name { flex: 1; }
    .meal-item .food-info { color: var(--text-secondary); font-size: 12px; text-align: right; min-width: 100px; }
    .meal-subtotal { background: #FAFAFA; padding: 8px 14px; font-size: 12px; color: var(--primary); font-weight: 600; text-align: right; border-top: 1px solid #EEE; }
    .summary-bar { background: linear-gradient(135deg, #E8F5E9, #C8E6C9); padding: 12px 16px; border-radius: 8px; margin-top: 8px; display: flex; justify-content: space-around; text-align: center; font-size: 13px; }
    .summary-bar .sum-num { font-size: 20px; font-weight: 700; color: var(--success); }
    .alert { padding: 10px 14px; border-radius: 8px; font-size: 12px; margin-top: 8px; line-height: 1.6; }
    .alert-warning { background: #FFF8E1; border: 1px solid #FFE082; color: #E65100; }
    .alert-danger { background: #FFEBEE; border: 1px solid #EF9A9A; color: #C62828; }
    .alert-info { background: #E3F2FD; border: 1px solid #90CAF9; color: #1565C0; }
    .hidden { display: none !important; }
    .loading { display: inline-block; width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff; border-radius: 50%; animation: spin 0.6s linear infinite; vertical-align: middle; margin-right: 6px; }
    @keyframes spin { to { transform: rotate(360deg); } }
    .toast { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background: #333; color: #fff; padding: 10px 20px; border-radius: 20px; font-size: 14px; z-index: 9999; opacity: 0; transition: opacity 0.3s; pointer-events: none; }
    .toast.show { opacity: 1; }
    .qr-container { text-align: center; margin: 12px 0; }
    .qr-container img { max-width: 200px; border: 1px solid var(--border); border-radius: 8px; padding: 8px; background: #fff; }
    .tab-bar { display: flex; gap: 4px; margin-bottom: 12px; }
    .tab-bar button { flex: 1; padding: 10px; border: 1px solid var(--border); background: #fff; border-radius: 8px; font-size: 13px; cursor: pointer; font-family: var(--font); color: var(--text-secondary); }
    .tab-bar button.active { background: var(--primary); color: #fff; border-color: var(--primary); font-weight: 600; }
    .patient-row { display: flex; justify-content: space-between; align-items: center; padding: 12px; border-bottom: 1px solid var(--border); cursor: pointer; transition: background 0.15s; }
    .patient-row:hover { background: #F5F7FA; }
    .patient-row .p-name { font-weight: 600; color: var(--primary); }
    .patient-row .p-info { font-size: 12px; color: var(--text-secondary); }
    .patient-row .p-date { font-size: 11px; color: #999; }
    .search-box { width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 15px; margin-bottom: 10px; font-family: var(--font); }
    .empty-state { text-align: center; padding: 40px 20px; color: #999; }
    .empty-state .icon { font-size: 48px; margin-bottom: 12px; }
    .modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 1000; display: flex; align-items: center; justify-content: center; }
    .modal { background: #fff; border-radius: var(--radius); padding: 24px; max-width: 400px; width: 90%; max-height: 80vh; overflow-y: auto; }
    .modal h3 { margin-bottom: 16px; color: var(--primary); }
    .modal .close { float: right; cursor: pointer; font-size: 20px; color: #999; background: none; border: none; }
    @media print {
        body { background: #fff; }
        .card { box-shadow: none; border: 1px solid #ddd; }
        .btn, .btn-row, .form-section-title, #input-section, .header, .tab-bar, .modal-overlay { display: none; }
        .container { max-width: 100%; }
    }
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>🥚 OHSS 高蛋白饮食智能计算器</h1>
        <div class="subtitle">生殖医学中心 · 护理宣教工具</div>
        <div class="user-bar">
            <span>👩‍⚕️ {{ user_name }}</span>
            <a href="/logout">退出登录</a>
        </div>
    </div>

    <div class="tab-bar">
        <button class="active" onclick="switchTab('calc')">📋 新建计算</button>
        <button onclick="switchTab('list')">📂 患者记录</button>
    </div>

    <!-- ====== 新建计算 ====== -->
    <div id="tab-calc">
        <div class="card" id="input-section">
            <div class="card-title">患者信息录入</div>
            <div class="form-row">
                <div class="form-group"><label>姓名 *</label><input type="text" id="patientName" placeholder="请输入姓名"></div>
                <div class="form-group"><label>年龄（岁）*</label><input type="number" id="patientAge" placeholder="年龄" min="18" max="60" step="1"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>身高（cm）*</label><input type="number" id="height" placeholder="例如 160" min="100" max="220" step="0.1"></div>
                <div class="form-group"><label>体重（kg）*</label><input type="number" id="weight" placeholder="例如 60" min="30" max="200" step="0.1"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>性别</label><select id="gender"><option value="female">女</option><option value="male">男</option></select></div>
                <div class="form-group"><label>腰围（cm）<span class="form-hint">选填</span></label><input type="number" id="waist" placeholder="腰围" min="40" max="200" step="0.1"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>小腿围（cm）<span class="form-hint">选填</span></label><input type="number" id="calf" placeholder="小腿围" min="20" max="80" step="0.1"></div>
                <div class="form-group"><label>评估阶段</label><select id="evalStage"><option value="baseline">基线评估（促排第一天）</option><option value="follicle14">第一次评估（卵泡≥14mm）</option><option value="hcg">第二次评估（HCG 日）</option><option value="retrieval">第三次评估（取卵日）</option><option value="day3">第四次评估（取卵后第3天）</option><option value="day5">第五次评估（取卵后第4/5天）</option></select></div>
            </div>
            <div class="form-section-title">🔬 风险评估指标</div>
            <div class="form-row">
                <div class="form-group"><label>PCOS 病史</label><select id="pcos"><option value="no">否</option><option value="yes">是</option></select></div>
                <div class="form-group"><label>既往 OHSS 病史</label><select id="prevOhss"><option value="no">否</option><option value="yes">是</option></select></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>AMH > 3.36 ng/ml</label><select id="amhHigh"><option value="no">否</option><option value="yes">是</option></select></div>
                <div class="form-group"><label>AFC ≥ 24 个</label><select id="afcHigh"><option value="no">否</option><option value="yes">是</option></select></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>E2 ≥ 3500 pg/ml</label><select id="e2High"><option value="no">否</option><option value="yes">是</option></select></div>
                <div class="form-group"><label>卵泡 ≥ 20 个（≥10mm）</label><select id="follicleHigh"><option value="no">否</option><option value="yes">是</option></select></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>获卵 ≥ 15 枚</label><select id="oocyteHigh"><option value="no">否</option><option value="yes">是</option></select></div>
                <div class="form-group"><label>临床症状</label><select id="symptoms"><option value="no">无症状</option><option value="yes">有症状（腹胀/腹痛/恶心/尿少）</option></select></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>卵巢增大（≥8cm）</label><select id="ovaryEnlarged"><option value="no">否</option><option value="yes">是</option></select></div>
                <div class="form-group"><label>腹水/盆腔积液</label><select id="ascites"><option value="no">无</option><option value="yes">有</option></select></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>胸水</label><select id="pleuralEffusion"><option value="no">无</option><option value="yes">有</option></select></div>
            </div>
            <button class="btn btn-primary" onclick="calculateAll()">🔍 计算并生成个性化食谱</button>
        </div>

        <div class="card hidden" id="result-section">
            <div class="card-title">📊 计算结果</div>
            <div class="result-grid" id="resultGrid"></div>
            <div id="riskBadgeContainer" style="margin-top:10px;text-align:center;"></div>
        </div>

        <div class="card hidden" id="meal-section">
            <div class="card-title">🍽️ 五餐个性化食谱</div>
            <div id="mealContent"></div>
            <div id="mealSummary"></div>
            <div style="margin-top:12px;"><button class="btn btn-outline btn-sm" onclick="regenerateMeals()">🔄 重新生成食谱</button></div>
        </div>

        <div class="card hidden" id="output-section">
            <div class="card-title">📄 报告输出</div>
            <div class="btn-row">
                <button class="btn btn-primary" onclick="downloadPDF()">📥 下载 PDF 报告</button>
                <button class="btn btn-outline" onclick="showQRCode()">📱 查看二维码</button>
            </div>
            <div class="qr-container hidden" id="qrContainer">
                <img id="qrImage" src="" alt="二维码" style="max-width:200px;">
                <p style="font-size:11px;color:#999;margin-top:6px;">患者手机扫码即可查看报告</p>
            </div>
        </div>
    </div>

    <!-- ====== 患者记录 ====== -->
    <div id="tab-list" class="hidden">
        <div class="card">
            <div class="card-title">📂 患者记录</div>
            <input type="text" class="search-box" id="searchInput" placeholder="🔍 搜索患者姓名..." oninput="loadPatientList()">
            <div id="patientList"></div>
        </div>
    </div>

    <!-- ====== 患者详情弹窗 ====== -->
    <div class="modal-overlay hidden" id="patientModal">
        <div class="modal">
            <button class="close" onclick="closeModal()">&times;</button>
            <h3>📋 患者详情</h3>
            <div id="patientDetail"></div>
            <div style="margin-top:16px;display:flex;gap:8px;">
                <button class="btn btn-outline btn-sm" onclick="closeModal()" style="flex:1;">关闭</button>
                <button class="btn btn-danger btn-sm" onclick="deletePatient()" style="flex:0;">🗑 删除</button>
            </div>
        </div>
    </div>

    <div class="card">
        <div class="card-title">⚠️ 安全提示</div>
        <div class="alert alert-warning">
            <strong>重要提醒：</strong><br>
            • 本工具为护理科普参考，<strong>不替代临床诊断</strong>。<br>
            • 30ml/kg 液体值仅作参考，<strong>口渴感、尿量优先</strong>，禁止机械限水。<br>
            • 治疗级（≥11 分）患者应尽快到急诊留观室就诊。<br>
            • 低盐饮食，少食多餐；严重腹胀/恶心时不要硬吃，立即联系科室或急诊。<br>
            • 如出现 24h 尿量 &lt; 500ml、体重日增 &gt; 1kg、呼吸困难，<strong>立即就诊！</strong>
        </div>
    </div>

    <div style="text-align:center;padding:16px;color:#999;font-size:12px;">
        生殖医学中心 · OHSS 高蛋白饮食智能计算器 v2.0<br>
        本工具评分量表为本科室自制，有待临床数据验证
    </div>
</div>

<div class="toast" id="toast"></div>

<script>
let currentMealPlan = null, currentCalcResult = null, currentRisk = null, currentPatient = null;
let currentPatientId = null, currentViewPatientId = null;

function $(id) { return document.getElementById(id); }
function val(id) { const el = $(id); if (!el) return null; const v = el.value.trim(); if (v === '') return null; const num = parseFloat(v); return isNaN(num) ? v : num; }
function showToast(msg, duration = 2000) { const t = $('toast'); t.textContent = msg; t.classList.add('show'); setTimeout(() => t.classList.remove('show'), duration); }
function showSection(id) { const el = $(id); if (el) el.classList.remove('hidden'); }
function hideSection(id) { const el = $(id); if (el) el.classList.add('hidden'); }

function switchTab(tab) {
    document.querySelectorAll('.tab-bar button').forEach((b,i) => b.classList.toggle('active', (tab==='calc'&&i===0)||(tab==='list'&&i===1)));
    $('tab-calc').classList.toggle('hidden', tab !== 'calc');
    $('tab-list').classList.toggle('hidden', tab !== 'list');
    if (tab === 'list') loadPatientList();
}

function calcBMI(weight, heightCm) { const h = heightCm / 100; return parseFloat((weight / (h * h)).toFixed(1)); }
function bmiCategory(bmi) { if (bmi < 18.5) return '消瘦'; if (bmi < 24) return '正常'; if (bmi < 28) return '超重'; return '肥胖'; }
function calcIBW(heightCm) { return heightCm - 105; }
function calcAdjustedWeight(actual, ibw) { const excess = actual - ibw; if (excess <= 0) return ibw; return parseFloat((ibw + 0.25 * excess).toFixed(1)); }
function determineCalcWeight(actual, heightCm, waist, calf, gender) {
    const bmi = calcBMI(actual, heightCm); const ibw = calcIBW(heightCm);
    if (bmi < 24) return { weight: actual, method: '实际体重（BMI ' + bmiCategory(bmi) + '）' };
    const waistThreshold = gender === 'female' ? 85 : 90;
    const calfThreshold = gender === 'female' ? 33 : 34;
    const hasWaist = waist !== null && waist > 0;
    const hasCalf = calf !== null && calf > 0;
    if (hasCalf && calf < calfThreshold) return { weight: actual, method: '肌少型肥胖→实际体重' };
    if (hasWaist && waist >= waistThreshold) return { weight: ibw, method: '向心性肥胖→理想体重' };
    if (hasWaist && waist < waistThreshold) return { weight: calcAdjustedWeight(actual, ibw), method: '周围型肥胖→校正体重' };
    if (hasCalf) return { weight: ibw, method: '默认理想体重（未测量腰围）' };
    return { weight: ibw, method: '默认理想体重（未测量腰围/小腿围）' };
}
function calcRiskScoreLocal() {
    let score = 0;
    ['pcos', 'prevOhss', 'amhHigh', 'afcHigh'].forEach(id => { const el = $(id); if (el && el.value === 'yes') score += 1; });
    const age = val('patientAge'); if (age !== null && age < 35) score += 1;
    const weight = val('weight'), height = val('height');
    if (weight && height) { const bmi = calcBMI(weight, height); if (bmi < 18.5) score += 1; }
    ['e2High', 'follicleHigh', 'oocyteHigh', 'symptoms', 'ovaryEnlarged', 'ascites', 'pleuralEffusion'].forEach(id => { const el = $(id); if (el && el.value === 'yes') score += 3; });
    return score;
}
function riskLevelLocal(score) {
    if (score === 0) return { level: '健康饮食级', coeff: [1.0, 1.2], cssClass: 'risk-healthy' };
    if (score <= 4) return { level: '预防级', coeff: [1.2, 1.5], cssClass: 'risk-prevention' };
    if (score <= 10) return { level: '干预级', coeff: [1.5, 1.8], cssClass: 'risk-intervention' };
    return { level: '治疗级', coeff: [1.8, 2.0], cssClass: 'risk-treatment' };
}

function calculateAll() {
    const name = val('patientName') || '未知';
    const age = val('patientAge'), height = val('height'), weight = val('weight');
    const gender = val('gender') || 'female';
    const waist = val('waist'), calf = val('calf');
    const evalStage = val('evalStage') || 'baseline';
    if (!height || !weight) { showToast('请填写身高和体重'); return; }
    if (!age) { showToast('请填写年龄'); return; }
    const bmi = calcBMI(weight, height);
    const bmiCat = bmiCategory(bmi);
    const cw = determineCalcWeight(weight, height, waist, calf, gender);
    const score = calcRiskScoreLocal();
    const risk = riskLevelLocal(score);
    const proteinLow = parseFloat((cw.weight * risk.coeff[0]).toFixed(1));
    const proteinHigh = parseFloat((cw.weight * risk.coeff[1]).toFixed(1));
    const liquidTotal = Math.round(cw.weight * 30);
    currentPatient = { name, age, height, weight, gender, waist, calf, eval_stage: evalStage };
    currentCalcResult = { bmi, bmi_category: bmiCat, calc_weight: cw.weight, calc_weight_method: cw.method, protein_low: proteinLow, protein_high: proteinHigh, liquid_total: liquidTotal };
    currentRisk = { score, level: risk.level, protein_coeff: risk.coeff[0] + '-' + risk.coeff[1] + ' g/kg/天', cssClass: risk.cssClass };
    renderResults();
    generateMealPlanLocal(proteinHigh, liquidTotal, cw.weight);
    showSection('output-section');
    hideSection('qrContainer');
    document.getElementById('result-section').scrollIntoView({ behavior: 'smooth' });
    savePatient();
}

function renderResults() {
    const r = currentCalcResult, risk = currentRisk;
    $('resultGrid').innerHTML =
        '<div class="result-item"><div class="label">BMI</div><div class="value">' + r.bmi + ' <span style="font-size:12px;color:#666;">kg/m&sup2;</span></div><div style="font-size:11px;color:#999;">' + r.bmi_category + '</div></div>' +
        '<div class="result-item"><div class="label">计算体重</div><div class="value-sm">' + r.calc_weight + ' <span style="font-size:12px;color:#666;">kg</span></div><div style="font-size:10px;color:#999;">' + r.calc_weight_method + '</div></div>' +
        '<div class="result-item"><div class="label">风险评分</div><div class="value">' + risk.score + ' <span style="font-size:12px;color:#666;">分</span></div></div>' +
        '<div class="result-item"><div class="label">风险等级</div><div class="value-sm"><span class="risk-badge ' + risk.cssClass + '">' + risk.level + '</span></div></div>' +
        '<div class="result-item"><div class="label">每日蛋白需求</div><div class="value-sm">' + r.protein_low + '~' + r.protein_high + ' <span style="font-size:12px;">g</span></div><div style="font-size:10px;color:#999;">' + risk.protein_coeff + '</div></div>' +
        '<div class="result-item"><div class="label">液体参考总量</div><div class="value-sm">' + r.liquid_total + ' <span style="font-size:12px;">ml</span></div><div style="font-size:10px;color:#999;">30ml/kg</div></div>';
    $('riskBadgeContainer').innerHTML = risk.level === '治疗级' ? '<div class="alert alert-danger" style="margin-top:8px;"><strong>⚠️ 治疗级警告：</strong>患者应尽快转诊至急诊留观室进行液体治疗！</div>' : '';
    showSection('result-section');
}

const FOOD_DB = ''' + json.dumps(FOOD_DATABASE, ensure_ascii=False) + r''';
const MEAL_CFG = ''' + json.dumps(MEAL_STRUCTURE, ensure_ascii=False) + r''';

function generateMealPlanLocal(targetProteinHigh, liquidTotal, calcWeight) {
    const proteinBudget = targetProteinHigh * 0.9;
    const meals = {}; let totalProtein = 0, totalWater = 0;
    for (const [mealName, config] of Object.entries(MEAL_CFG)) {
        const mealTarget = proteinBudget * config.protein_ratio;
        const mealItems = []; let mealProtein = 0, mealWater = 0;
        let available = FOOD_DB.filter(f => config.categories.includes(f.category));
        for (let i = 0; i < config.max_items; i++) {
            if (mealProtein >= mealTarget) break;
            const existingNames = new Set(mealItems.map(mi => mi.name));
            const remaining = available.filter(f => !existingNames.has(f.name));
            if (remaining.length === 0) break;
            remaining.sort((a, b) => (b.protein / Math.max(b.unit_g, 1)) - (a.protein / Math.max(a.unit_g, 1)));
            let best = remaining[0];
            if (mealProtein + best.protein > mealTarget * 1.2) {
                const smaller = remaining.filter(c => mealProtein + c.protein <= mealTarget * 1.2);
                if (smaller.length > 0) best = smaller[0]; else break;
            }
            mealItems.push({ name: best.name, portion: best.portion, quantity: 1, protein: best.protein, water: best.water, category: best.category });
            mealProtein += best.protein; mealWater += best.water;
        }
        meals[mealName] = { label: config.description, items: mealItems, protein_subtotal: parseFloat(mealProtein.toFixed(1)), water_subtotal: mealWater };
        totalProtein += mealProtein; totalWater += mealWater;
    }
    totalProtein = parseFloat(totalProtein.toFixed(1));
    if (totalProtein > targetProteinHigh) {
        let excess = totalProtein - targetProteinHigh;
        for (const category of ['营养补充剂', '豆制品', '奶制品']) {
            if (excess <= 0) break;
            for (const mealName of Object.keys(meals)) {
                if (excess <= 0) break;
                const meal = meals[mealName];
                for (let i = meal.items.length - 1; i >= 0; i--) {
                    if (excess <= 0) break;
                    const item = meal.items[i];
                    if (item.category === category) {
                        meal.items.splice(i, 1);
                        meal.protein_subtotal = parseFloat((meal.protein_subtotal - item.protein).toFixed(1));
                        meal.water_subtotal -= item.water;
                        totalProtein = parseFloat((totalProtein - item.protein).toFixed(1));
                        totalWater -= item.water; excess -= item.protein;
                    }
                }
            }
        }
    }
    const liquidTotalInt = Math.round(liquidTotal);
    currentMealPlan = { meals, total_protein: parseFloat(totalProtein.toFixed(1)), total_food_water: totalWater, liquid_total: liquidTotalInt, actual_drink: Math.max(0, liquidTotalInt - totalWater), protein_target_high: targetProteinHigh };
    renderMeals(); showSection('meal-section');
}

function renderMeals() {
    if (!currentMealPlan) return;
    const plan = currentMealPlan; let html = '';
    for (const [mealName, meal] of Object.entries(plan.meals)) {
        html += '<div class="meal-section"><div class="meal-header"><span>' + mealName + '</span><span class="meal-time">' + meal.label + '</span></div><div class="meal-items">';
        if (meal.items.length === 0) { html += '<div class="meal-item" style="color:#999;">暂无推荐食物</div>'; }
        else { meal.items.forEach(item => { html += '<div class="meal-item"><span class="food-name">' + item.name + '</span><span class="food-info">' + item.portion + ' · ' + item.protein + 'g 蛋白 · ' + item.water + 'ml 水</span></div>'; }); }
        html += '</div><div class="meal-subtotal">' + mealName + '小计：' + meal.protein_subtotal + 'g 蛋白 · ' + meal.water_subtotal + 'ml 食物水</div></div>';
    }
    $('mealContent').innerHTML = html;
    $('mealSummary').innerHTML = '<div class="summary-bar"><div><div style="color:#666;">每日总蛋白</div><div class="sum-num">' + plan.total_protein + 'g</div><div style="font-size:11px;color:#999;">上限 ' + plan.protein_target_high + 'g</div></div><div><div style="color:#666;">食物含水量</div><div class="sum-num">' + plan.total_food_water + 'ml</div></div><div><div style="color:#666;">液体总量</div><div class="sum-num">' + plan.liquid_total + 'ml</div><div style="font-size:11px;color:#999;">30ml/kg</div></div><div><div style="color:#666;">建议饮水量</div><div class="sum-num">' + plan.actual_drink + 'ml</div><div style="font-size:11px;color:#999;">口渴优先</div></div></div>';
}

function regenerateMeals() {
    if (!currentCalcResult || !currentRisk) { showToast('请先计算'); return; }
    generateMealPlanLocal(currentCalcResult.protein_high, currentCalcResult.liquid_total, currentCalcResult.calc_weight);
    showToast('食谱已重新生成 ✓');
}

async function savePatient() {
    if (!currentPatient || !currentCalcResult || !currentRisk) return;
    try {
        const resp = await fetch('/api/patients', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ patient: currentPatient, calc_result: currentCalcResult, risk: currentRisk, meal_plan: currentMealPlan })
        });
        if (resp.ok) {
            const data = await resp.json();
            currentPatientId = data.id;
            showToast('患者信息已保存 ✓');
        }
    } catch (e) { console.error('保存失败:', e); }
}

async function downloadPDF() {
    if (!currentPatient || !currentCalcResult || !currentRisk) { showToast('请先完成计算'); return; }
    const btn = event.target; const origText = btn.innerHTML;
    btn.innerHTML = '<span class="loading"></span>生成中...'; btn.disabled = true;
    try {
        const resp = await fetch('/api/pdf', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ patient: currentPatient, calc_result: currentCalcResult, risk: currentRisk, meal_plan: currentMealPlan || { meals: {}, total_protein: 0, total_food_water: 0 } }) });
        if (!resp.ok) { const err = await resp.json(); throw new Error(err.error || 'PDF 生成失败'); }
        const blob = await resp.blob(); const url = URL.createObjectURL(blob);
        const a = document.createElement('a'); a.href = url; a.download = 'OHSS食谱_' + (currentPatient.name || '患者') + '.pdf';
        document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(url);
        showToast('PDF 下载成功 ✓');
    } catch (e) { showToast('生成失败：' + e.message); }
    finally { btn.innerHTML = origText; btn.disabled = false; }
}

async function showQRCode() {
    if (!currentPatientId) { showToast('请先完成计算并保存'); return; }
    const container = $('qrContainer');
    if (!container.classList.contains('hidden')) { container.classList.add('hidden'); return; }
    const img = $('qrImage');
    img.src = '/api/qrcode/' + currentPatientId;
    container.classList.remove('hidden');
    showToast('二维码已生成，手机扫码即可查看 ✓');
}

async function loadPatientList() {
    const search = ($('searchInput').value || '').trim();
    const url = search ? '/api/patients?search=' + encodeURIComponent(search) : '/api/patients';
    try {
        const resp = await fetch(url);
        const patients = await resp.json();
        const container = $('patientList');
        if (!patients.length) {
            container.innerHTML = '<div class="empty-state"><div class="icon">📭</div><p>暂无患者记录</p></div>';
            return;
        }
        container.innerHTML = patients.map(p => {
            const date = new Date(p.created_at).toLocaleDateString('zh-CN');
            const riskBadge = p.risk_level || '';
            const riskClass = riskBadge.includes('治疗') ? 'risk-treatment' : riskBadge.includes('干预') ? 'risk-intervention' : riskBadge.includes('预防') ? 'risk-prevention' : 'risk-healthy';
            return '<div class="patient-row" onclick="viewPatient(' + p.id + ')">' +
                '<div><div class="p-name">' + escapeHtml(p.name) + ' <span class="risk-badge ' + riskClass + '" style="font-size:11px;">' + riskBadge + '</span></div>' +
                '<div class="p-info">BMI ' + (p.bmi||'-') + ' · ' + (p.calc_weight||'-') + 'kg · 蛋白 ' + (p.protein_low||'') + '~' + (p.protein_high||'') + 'g</div></div>' +
                '<div class="p-date">' + date + '</div></div>';
        }).join('');
    } catch (e) { console.error('加载患者列表失败:', e); }
}

function escapeHtml(str) {
    const div = document.createElement('div'); div.textContent = str; return div.innerHTML;
}

async function viewPatient(id) {
    currentViewPatientId = id;
    try {
        const resp = await fetch('/api/patients/' + id);
        const p = await resp.json();
        const riskBadge = p.risk_level || '';
        const riskClass = riskBadge.includes('治疗') ? 'risk-treatment' : riskBadge.includes('干预') ? 'risk-intervention' : riskBadge.includes('预防') ? 'risk-prevention' : 'risk-healthy';
        let html = '<div class="result-grid">' +
            '<div class="result-item"><div class="label">姓名</div><div class="value-sm">' + escapeHtml(p.name) + '</div></div>' +
            '<div class="result-item"><div class="label">年龄</div><div class="value-sm">' + (p.age||'-') + ' 岁</div></div>' +
            '<div class="result-item"><div class="label">身高</div><div class="value-sm">' + p.height + ' cm</div></div>' +
            '<div class="result-item"><div class="label">体重</div><div class="value-sm">' + p.weight + ' kg</div></div>' +
            '<div class="result-item"><div class="label">BMI</div><div class="value-sm">' + (p.bmi||'-') + ' (' + (p.bmi_category||'') + ')</div></div>' +
            '<div class="result-item"><div class="label">计算体重</div><div class="value-sm">' + (p.calc_weight||'-') + ' kg</div></div>' +
            '<div class="result-item"><div class="label">风险评分</div><div class="value">' + (p.risk_score||'-') + ' 分</div></div>' +
            '<div class="result-item"><div class="label">风险等级</div><div class="value-sm"><span class="risk-badge ' + riskClass + '">' + riskBadge + '</span></div></div>' +
            '<div class="result-item"><div class="label">每日蛋白</div><div class="value-sm">' + (p.protein_low||'') + '~' + (p.protein_high||'') + ' g</div></div>' +
            '<div class="result-item"><div class="label">液体总量</div><div class="value-sm">' + (p.liquid_total||'') + ' ml</div></div>' +
            '</div>';
        // Meal plan
        if (p.meal_plan_json) {
            try {
                const mp = JSON.parse(p.meal_plan_json);
                html += '<div style="margin-top:12px;"><strong>🍽️ 食谱总蛋白：</strong>' + (mp.total_protein||0) + 'g · 实际饮水：' + (mp.actual_drink||0) + 'ml</div>';
            } catch(e) {}
        }
        html += '<div style="font-size:11px;color:#999;margin-top:8px;">创建时间：' + new Date(p.created_at).toLocaleString('zh-CN') + '</div>';
        $('patientDetail').innerHTML = html;
        $('patientModal').classList.remove('hidden');
    } catch (e) { showToast('加载失败'); }
}

function closeModal() { $('patientModal').classList.add('hidden'); currentViewPatientId = null; }

async function deletePatient() {
    if (!currentViewPatientId) return;
    if (!confirm('确定删除该患者记录吗？此操作不可撤销。')) return;
    try {
        const resp = await fetch('/api/patients/' + currentViewPatientId, { method: 'DELETE' });
        if (resp.ok) { showToast('已删除 ✓'); closeModal(); loadPatientList(); }
        else { const err = await resp.json(); showToast('删除失败：' + err.error); }
    } catch (e) { showToast('删除失败'); }
}

document.addEventListener('DOMContentLoaded', function() {
    hideSection('result-section'); hideSection('meal-section'); hideSection('output-section');
});
</script>
</body>
</html>
'''

# 登录页面模板
LOGIN_TEMPLATE = r'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OHSS 计算器 - 登录</title>
<style>
    :root { --primary: #2B5797; --primary-light: #4472C4; --bg: #F5F7FA; --card-bg: #FFFFFF; --text: #212121; --border: #E0E0E0; --radius: 10px; --font: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: var(--font); background: linear-gradient(160deg, #0f2440, #1a3a5c, #2B5797); min-height: 100vh; display: flex; align-items: center; justify-content: center; }
    .login-card { background: var(--card-bg); border-radius: 16px; padding: 40px; width: 360px; max-width: 90%; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
    .login-card h1 { font-size: 22px; color: var(--primary); text-align: center; margin-bottom: 4px; }
    .login-card .subtitle { text-align: center; color: #999; font-size: 13px; margin-bottom: 28px; }
    .form-group { margin-bottom: 16px; }
    .form-group label { display: block; font-size: 13px; color: #666; margin-bottom: 6px; font-weight: 500; }
    .form-group input { width: 100%; padding: 12px 14px; border: 1px solid var(--border); border-radius: 8px; font-size: 16px; font-family: var(--font); transition: border-color 0.2s; }
    .form-group input:focus { outline: none; border-color: var(--primary-light); box-shadow: 0 0 0 3px rgba(68,114,196,0.1); }
    .btn { width: 100%; padding: 12px; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; background: linear-gradient(135deg, var(--primary), var(--primary-light)); color: #fff; font-family: var(--font); }
    .btn:active { transform: scale(0.97); }
    .error { color: #C62828; font-size: 13px; text-align: center; margin-bottom: 12px; padding: 8px; background: #FFEBEE; border-radius: 6px; display: none; }
    .error.show { display: block; }
</style>
</head>
<body>
<div class="login-card">
    <h1>🥚 OHSS 计算器</h1>
    <p class="subtitle">生殖医学中心 · 护士登录</p>
    <div class="error" id="error">{{ error or '' }}</div>
    <form method="POST" action="/login">
        <div class="form-group"><label>用户名</label><input type="text" name="username" placeholder="请输入用户名" required autofocus></div>
        <div class="form-group"><label>密码</label><input type="password" name="password" placeholder="请输入密码" required></div>
        <button type="submit" class="btn">登 录</button>
    </form>
</div>
</body>
</html>
'''

# ============================================================
# 路由
# ============================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        if user and verify_password(password, user['password_hash']):
            session['user_id'] = user['id']
            session['user_name'] = user['display_name']
            session['user_role'] = user['role']
            return redirect('/')

        return render_template_string(LOGIN_TEMPLATE, error='用户名或密码错误')

    return render_template_string(LOGIN_TEMPLATE, error='')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/')
@login_required
def index():
    return render_template_string(HTML_TEMPLATE, user_name=session.get('user_name', ''))

# ============================================================
# API 路由
# ============================================================

@app.route('/api/calculate', methods=['POST'])
@login_required
def calculate():
    try:
        data = request.get_json()
        if not data: return jsonify({'error': '无效的请求数据'}), 400
        height = float(data.get('height', 0))
        weight = float(data.get('weight', 0))
        gender = data.get('gender', 'female')
        waist = data.get('waist')
        calf = data.get('calf')
        age = data.get('age')
        if not height or not weight: return jsonify({'error': '身高和体重为必填项'}), 400
        bmi = calc_bmi(weight, height)
        bmi_cat = bmi_category(bmi)
        calc_w, calc_w_method = determine_calc_weight(weight, height, float(waist) if waist else None, float(calf) if calf else None, gender)
        assessment = {
            'pcos': data.get('pcos') == 'yes', 'prev_ohss': data.get('prev_ohss') == 'yes',
            'age_under_35': age is not None and float(age) < 35, 'bmi_under_18_5': bmi < 18.5,
            'amh_high': data.get('amh_high') == 'yes', 'afc_high': data.get('afc_high') == 'yes',
            'e2_high': data.get('e2_high') == 'yes', 'follicle_high': data.get('follicle_high') == 'yes',
            'oocyte_high': data.get('oocyte_high') == 'yes', 'symptoms': data.get('symptoms') == 'yes',
            'ovary_enlarged': data.get('ovary_enlarged') == 'yes', 'ascites': data.get('ascites') == 'yes',
            'pleural_effusion': data.get('pleural_effusion') == 'yes',
        }
        score = calc_risk_score(assessment)
        level, coeff = risk_level(score)
        protein_low, protein_high = calc_protein_range(calc_w, coeff)
        liquid_total = calc_liquid_total(calc_w)
        meal_plan = generate_meal_plan(protein_high, liquid_total, calc_w)
        return jsonify({
            'patient': {'name': data.get('name', ''), 'age': age, 'height': height, 'weight': weight, 'gender': gender, 'waist': waist, 'calf': calf},
            'calc_result': {'bmi': bmi, 'bmi_category': bmi_cat, 'calc_weight': calc_w, 'calc_weight_method': calc_w_method, 'protein_low': protein_low, 'protein_high': protein_high, 'liquid_total': liquid_total, 'actual_drink': meal_plan['actual_drink']},
            'risk': {'score': score, 'level': level, 'protein_coeff': f"{coeff[0]}-{coeff[1]} g/kg/天"},
            'meal_plan': meal_plan,
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# -------- 患者管理 API --------

@app.route('/api/patients', methods=['GET'])
@login_required
def list_patients():
    search = request.args.get('search', '').strip()
    conn = get_db()
    if search:
        rows = conn.execute(
            "SELECT id, name, age, bmi, bmi_category, calc_weight, protein_low, protein_high, liquid_total, risk_score, risk_level, created_at FROM patients WHERE name LIKE ? ORDER BY created_at DESC LIMIT 50",
            (f'%{search}%',)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, name, age, bmi, bmi_category, calc_weight, protein_low, protein_high, liquid_total, risk_score, risk_level, created_at FROM patients ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/patients', methods=['POST'])
@login_required
def create_patient():
    try:
        data = request.get_json()
        patient = data.get('patient', {})
        calc_result = data.get('calc_result', {})
        risk = data.get('risk', {})
        meal_plan = data.get('meal_plan', {})

        conn = get_db()
        cursor = conn.execute(
            """INSERT INTO patients (name, age, height, weight, gender, waist, calf, eval_stage, bmi, bmi_category, calc_weight, calc_weight_method, protein_low, protein_high, liquid_total, actual_drink, risk_score, risk_level, protein_coeff, meal_plan_json, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                patient.get('name', ''), patient.get('age'), patient.get('height'), patient.get('weight'),
                patient.get('gender', 'female'), patient.get('waist'), patient.get('calf'), patient.get('eval_stage'),
                calc_result.get('bmi'), calc_result.get('bmi_category'), calc_result.get('calc_weight'),
                calc_result.get('calc_weight_method'), calc_result.get('protein_low'), calc_result.get('protein_high'),
                calc_result.get('liquid_total'), calc_result.get('actual_drink'),
                risk.get('score'), risk.get('level'), risk.get('protein_coeff'),
                json.dumps(meal_plan, ensure_ascii=False) if meal_plan else None,
                session.get('user_id')
            )
        )
        conn.commit()
        patient_id = cursor.lastrowid
        conn.close()
        return jsonify({'id': patient_id, 'message': '保存成功'})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/patients/<int:patient_id>', methods=['GET'])
@login_required
def get_patient(patient_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    conn.close()
    if not row: return jsonify({'error': '患者不存在'}), 404
    return jsonify(dict(row))

@app.route('/api/patients/<int:patient_id>', methods=['DELETE'])
@login_required
def delete_patient(patient_id):
    conn = get_db()
    conn.execute("DELETE FROM patients WHERE id = ?", (patient_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': '已删除'})

# -------- PDF 报告 --------

@app.route('/api/pdf', methods=['POST'])
@login_required
def generate_pdf():
    try:
        data = request.get_json()
        if not data: return jsonify({'error': '无效的请求数据'}), 400
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=15*mm, bottomMargin=15*mm, leftMargin=15*mm, rightMargin=15*mm)
        styles = getSampleStyleSheet()
        if FONT_AVAILABLE:
            title_style = ParagraphStyle('CNTitle', fontName=FONT_NAME, fontSize=16, leading=24, alignment=TA_CENTER, spaceAfter=10)
            heading_style = ParagraphStyle('CNHeading', fontName=FONT_NAME, fontSize=12, leading=18, spaceBefore=10, spaceAfter=6)
            body_style = ParagraphStyle('CNBody', fontName=FONT_NAME, fontSize=10, leading=16, spaceAfter=4)
            small_style = ParagraphStyle('CNSmall', fontName=FONT_NAME, fontSize=8, leading=12, textColor=HexColor('#666666'))
        else:
            title_style = styles['Title']; heading_style = styles['Heading2']; body_style = styles['Normal']; small_style = styles['Normal']
        story = []
        story.append(Paragraph("OHSS 高蛋白饮食个性化食谱报告", title_style))
        story.append(Spacer(1, 5*mm))
        story.append(Paragraph("一、患者基本信息", heading_style))
        patient = data.get('patient', {})
        calc_result = data.get('calc_result', {})
        risk = data.get('risk', {})
        info_data = [
            ['姓名', patient.get('name', '-'), '年龄', str(patient.get('age', '-'))],
            ['身高', f"{patient.get('height', '-')} cm", '体重', f"{patient.get('weight', '-')} kg"],
            ['BMI', f"{calc_result.get('bmi', '-')} kg/m²", 'BMI 分类', calc_result.get('bmi_category', '-')],
            ['计算体重', f"{calc_result.get('calc_weight', '-')} kg", '计算体重方法', calc_result.get('calc_weight_method', '-')],
        ]
        for row in info_data:
            story.append(Paragraph(f"<b>{row[0]}：</b>{row[1]}　　<b>{row[2]}：</b>{row[3]}", body_style))
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph("二、风险评估结果", heading_style))
        risk_data = [
            ['风险评分', f"{risk.get('score', '-')} 分"], ['风险等级', risk.get('level', '-')],
            ['蛋白系数', risk.get('protein_coeff', '-')],
            ['每日蛋白需求', f"{calc_result.get('protein_low', '-')} ~ {calc_result.get('protein_high', '-')} g"],
            ['液体参考总量', f"{calc_result.get('liquid_total', '-')} ml (30ml/kg)"],
            ['实际建议饮水量', f"{calc_result.get('actual_drink', '-')} ml"],
        ]
        for row in risk_data:
            story.append(Paragraph(f"<b>{row[0]}：</b>{row[1]}", body_style))
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph("三、五餐食谱明细", heading_style))
        meal_plan = data.get('meal_plan', {}).get('meals', {})
        meal_table_data = [['餐次', '时间', '食物', '份量', '蛋白(g)', '含水(ml)']]
        for meal_name, meal in meal_plan.items():
            items = meal.get('items', [])
            if items:
                for i, item in enumerate(items):
                    meal_table_data.append([meal_name if i == 0 else '', meal.get('label', '') if i == 0 else '', item.get('name', ''), item.get('portion', ''), str(item.get('protein', '')), str(item.get('water', ''))])
                meal_table_data.append(['', '', f'【{meal_name}小计】', '', str(meal.get('protein_subtotal', '')), str(meal.get('water_subtotal', ''))])
            else:
                meal_table_data.append([meal_name, meal.get('label', ''), '（无）', '-', '0', '0'])
        total_protein = data.get('meal_plan', {}).get('total_protein', 0)
        total_water = data.get('meal_plan', {}).get('total_food_water', 0)
        meal_table_data.append(['', '', '【总计】', '', str(total_protein), str(total_water)])
        col_widths = [50, 70, 140, 80, 55, 55]
        meal_table = Table(meal_table_data, colWidths=col_widths, repeatRows=1)
        meal_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), FONT_FALLBACK), ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('FONTSIZE', (0, 0), (-1, 0), 9), ('BACKGROUND', (0, 0), (-1, 0), HexColor('#4472C4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#FFFFFF')), ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (4, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#CCCCCC')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#FFFFFF'), HexColor('#F2F7FB')]),
            ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(meal_table)
        story.append(Spacer(1, 5*mm))
        story.append(Paragraph("四、重要安全提示", heading_style))
        warnings = [
            "本工具为护理科普参考，不替代临床诊断。",
            "30ml/kg 液体值仅作参考，口渴感、尿量优先，禁止机械限水。",
            "治疗级（≥11 分）患者应尽快到急诊留观室就诊。",
            "低盐饮食，少食多餐；严重腹胀/恶心时不要硬吃，立即联系科室或急诊。",
            "如出现 24h 尿量 < 500ml、体重日增 > 1kg、呼吸困难，立即就诊！",
        ]
        for w in warnings: story.append(Paragraph(f"• {w}", body_style))
        story.append(Spacer(1, 10*mm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor('#CCCCCC')))
        story.append(Paragraph(f"生殖医学中心 · OHSS 高蛋白饮食智能计算器 · 生成日期：{datetime.now().strftime('%Y-%m-%d %H:%M')}", small_style))
        doc.build(story)
        buffer.seek(0)
        return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=f'OHSS食谱_{patient.get("name", "患者")}.pdf')
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# -------- 二维码（在线显示 + 数据精简） --------

@app.route('/api/qrcode/<int:patient_id>')
@login_required
def get_qrcode(patient_id):
    """生成可扫描的二维码图片（精简数据，在线显示）"""
    try:
        conn = get_db()
        row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
        conn.close()
        if not row: return jsonify({'error': '患者不存在'}), 404

        # 精简数据，使用短 key，确保二维码可扫描
        qr_info = {
            'n': row['name'],
            'h': row['height'],
            'w': row['weight'],
            'b': row['bmi'],
            'r': row['risk_level'],
            's': row['risk_score'],
            'p': f"{row['protein_low']}-{row['protein_high']}g",
            'l': f"{row['liquid_total']}ml",
            'd': f"{row['actual_drink']}ml",
        }
        qr_text = json.dumps(qr_info, ensure_ascii=False, separators=(',', ':'))

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(qr_text)
        qr.make(fit=True)

        img = qr.make_image(fill_color='black', back_color='white')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return send_file(buffer, mimetype='image/png')
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================================
# 启动
# ============================================================
if __name__ == '__main__':
    init_db()
    print("=" * 50)
    print("  OHSS 高蛋白饮食智能计算器 v2.0")
    print("  数据库: ohss.db (SQLite)")
    print("  默认账号: admin / ohss2024")
    print("  访问地址: http://localhost:5000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=os.environ.get('FLASK_DEBUG', '0') == '1')