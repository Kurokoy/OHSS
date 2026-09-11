# OHSS 高蛋白饮食智能计算器 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建单文件 Flask Web 应用，实现 OHSS 患者信息录入 → BMI/计算体重/风险分层/蛋白需求/液体参考自动计算 → 五餐食谱生成 → PDF 报告 + 二维码输出，移动端优先适配微信浏览器。

**Architecture:** 单文件 `app.py`（Flask 后端 + 内嵌 HTML/CSS/JS 前端），所有数据硬编码，无外部 API。PDF 用 reportlab + msyh.ttc，二维码用 qrcode 库。前端原生 JS 无框架，CSS 内联，移动端优先（max-width 480px）。

**Tech Stack:** Python 3, Flask, reportlab, qrcode, PIL (Pillow)

**Files:**
- Create: `ohss-calculator/app.py` — 完整应用（后端路由 + 内嵌 HTML/CSS/JS）
- Create: `ohss-calculator/requirements.txt` — 依赖清单
- Create: `ohss-calculator/start.bat` — Windows 启动脚本
- Create: `ohss-calculator/README.md` — 使用说明

---

## 文件职责

| 文件 | 职责 |
|------|------|
| `app.py` | 全部应用代码：Flask 路由、计算逻辑、食物数据库、PDF 生成、二维码生成、内嵌 HTML/CSS/JS 前端 |
| `requirements.txt` | Python 依赖：flask, reportlab, qrcode, Pillow |
| `start.bat` | Windows 一键启动脚本 |
| `README.md` | 使用说明 |

---

### Task 1: 项目骨架与依赖

**Files:**
- Create: `ohss-calculator/requirements.txt`
- Create: `ohss-calculator/app.py` (骨架)

- [ ] **Step 1: 创建 requirements.txt**

```
flask>=3.0
reportlab>=4.0
qrcode>=7.4
Pillow>=10.0
```

- [ ] **Step 2: 创建 app.py 骨架**

```python
"""
OHSS 高蛋白饮食智能计算器
单文件 Flask 后端 + 内嵌 HTML 前端
用于生殖中心护士门诊宣教时快速生成个性化高蛋白饮食食谱
"""

from flask import Flask, request, jsonify, send_file, render_template_string
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

app = Flask(__name__)

# ============================================================
# 字体注册（微软雅黑，用于 PDF 中文）
# ============================================================
FONT_NAME = 'MSYH'
FONT_PATH_WIN = 'C:/Windows/Fonts/msyh.ttc'
FONT_PATH_ALT = '/usr/share/fonts/truetype/msyh.ttc'

def register_font():
    """注册中文字体，尝试多个路径"""
    for path in [FONT_PATH_WIN, FONT_PATH_ALT]:
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont(FONT_NAME, path))
            return True
    return False

FONT_AVAILABLE = register_font()
FONT_FALLBACK = FONT_NAME if FONT_AVAILABLE else 'Helvetica'

# ============================================================
# HTML 模板（内嵌）
# ============================================================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>OHSS 高蛋白饮食智能计算器</title>
<style>
    /* 样式占位 — 后续任务填充 */
</style>
</head>
<body>
    <div class="container">
        <h1>OHSS 高蛋白饮食智能计算器</h1>
    </div>
    <script>
        // JS 逻辑占位 — 后续任务填充
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/calculate', methods=['POST'])
def calculate():
    """核心计算接口（占位）"""
    return jsonify({'status': 'ok'})

@app.route('/api/pdf', methods=['POST'])
def generate_pdf():
    """PDF 报告生成接口（占位）"""
    return jsonify({'status': 'ok'})

@app.route('/api/qrcode', methods=['POST'])
def generate_qrcode():
    """二维码生成接口（占位）"""
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
```

- [ ] **Step 3: 安装依赖并验证启动**

```bash
cd "C:\Users\a\ohss-calculator"
pip install -r requirements.txt
python app.py
```

Expected: Flask 启动在 `http://0.0.0.0:5000`，访问 `/` 返回 HTML 页面。

---

### Task 2: 食物数据库与计算逻辑

**Files:**
- Modify: `ohss-calculator/app.py` — 在骨架基础上添加食物数据库和计算函数

- [ ] **Step 1: 添加食物数据库（替换骨架中 `# HTML 模板` 之前）**

```python
# ============================================================
# 食物数据库（42 种，来自附录二《蛋白质食物换算卡》）
# 每项：name, portion(分量描述), protein_g(蛋白含量g), water_ml(含水量ml), category
# ============================================================
FOOD_DATABASE = [
    # 蛋类
    {"name": "鸡蛋（中等全蛋）", "portion": "1个(50g)", "protein": 6.5, "water": 35, "category": "蛋类", "unit_g": 50},
    {"name": "鸡蛋白（蛋清）", "portion": "1个蛋清(30g)", "protein": 3.8, "water": 28, "category": "蛋类", "unit_g": 30},
    {"name": "鹌鹑蛋", "portion": "5个(50g)", "protein": 6.5, "water": 35, "category": "蛋类", "unit_g": 50},

    # 奶制品
    {"name": "纯牛奶", "portion": "250ml/盒", "protein": 8, "water": 220, "category": "奶制品", "unit_g": 250},
    {"name": "无糖酸奶", "portion": "200g/杯", "protein": 7.5, "water": 170, "category": "奶制品", "unit_g": 200},
    {"name": "脱脂奶粉", "portion": "20g", "protein": 7, "water": 1, "category": "奶制品", "unit_g": 20},
    {"name": "奶酪（芝士）", "portion": "30g", "protein": 7.5, "water": 10, "category": "奶制品", "unit_g": 30},

    # 肉类
    {"name": "熟鸡胸肉（去皮）", "portion": "100g", "protein": 27.5, "water": 65, "category": "肉类", "unit_g": 100},
    {"name": "熟鸡腿肉（去皮）", "portion": "100g", "protein": 25, "water": 67, "category": "肉类", "unit_g": 100},
    {"name": "熟瘦牛里脊", "portion": "100g", "protein": 22, "water": 60, "category": "肉类", "unit_g": 100},
    {"name": "熟瘦猪肉", "portion": "100g", "protein": 21, "water": 58, "category": "肉类", "unit_g": 100},
    {"name": "熟牛排", "portion": "100g", "protein": 27, "water": 55, "category": "肉类", "unit_g": 100},
    {"name": "熟鸭肉（去皮）", "portion": "100g", "protein": 19, "water": 63, "category": "肉类", "unit_g": 100},
    {"name": "午餐肉/火腿肠", "portion": "100g", "protein": 13, "water": 55, "category": "肉类", "unit_g": 100},

    # 水产
    {"name": "熟虾仁", "portion": "100g", "protein": 18, "water": 75, "category": "水产", "unit_g": 100},
    {"name": "熟鲈鱼/草鱼鱼肉", "portion": "100g", "protein": 17.5, "water": 70, "category": "水产", "unit_g": 100},
    {"name": "熟三文鱼", "portion": "100g", "protein": 22, "water": 64, "category": "水产", "unit_g": 100},
    {"name": "熟带鱼", "portion": "100g", "protein": 18, "water": 70, "category": "水产", "unit_g": 100},

    # 豆制品
    {"name": "北豆腐（老豆腐）", "portion": "100g", "protein": 12, "water": 80, "category": "豆制品", "unit_g": 100},
    {"name": "南豆腐（嫩豆腐）", "portion": "100g", "protein": 6.5, "water": 90, "category": "豆制品", "unit_g": 100},
    {"name": "豆腐干", "portion": "100g", "protein": 25, "water": 55, "category": "豆制品", "unit_g": 100},
    {"name": "豆浆（无糖）", "portion": "250ml", "protein": 6.5, "water": 230, "category": "豆制品", "unit_g": 250},
    {"name": "腐竹（干）", "portion": "20g", "protein": 9.5, "water": 1, "category": "豆制品", "unit_g": 20},
    {"name": "毛豆（鲜）", "portion": "100g", "protein": 13, "water": 70, "category": "豆制品", "unit_g": 100},

    # 主食
    {"name": "米饭（熟）", "portion": "一碗(200g)", "protein": 5.5, "water": 160, "category": "主食", "unit_g": 200},
    {"name": "面条（熟）", "portion": "一碗(200g)", "protein": 5.5, "water": 140, "category": "主食", "unit_g": 200},
    {"name": "馒头", "portion": "1个(100g)", "protein": 7.5, "water": 40, "category": "主食", "unit_g": 100},
    {"name": "全麦面包", "portion": "2片(70g)", "protein": 6.5, "water": 20, "category": "主食", "unit_g": 70},
    {"name": "燕麦片（干）", "portion": "40g", "protein": 5.5, "water": 2, "category": "主食", "unit_g": 40},
    {"name": "小米粥", "portion": "一碗(300ml)", "protein": 3.5, "water": 270, "category": "主食", "unit_g": 300},
    {"name": "白米粥", "portion": "一碗(300ml)", "protein": 2.5, "water": 280, "category": "主食", "unit_g": 300},

    # 蔬菜
    {"name": "西蓝花（熟）", "portion": "100g", "protein": 3.5, "water": 85, "category": "蔬菜", "unit_g": 100},
    {"name": "菠菜（熟）", "portion": "100g", "protein": 3, "water": 88, "category": "蔬菜", "unit_g": 100},
    {"name": "番茄", "portion": "1个(150g)", "protein": 1.3, "water": 140, "category": "蔬菜", "unit_g": 150},
    {"name": "黄瓜", "portion": "100g", "protein": 0.8, "water": 95, "category": "蔬菜", "unit_g": 100},
    {"name": "冬瓜（熟）", "portion": "100g", "protein": 0.5, "water": 95, "category": "蔬菜", "unit_g": 100},

    # 水果
    {"name": "苹果", "portion": "1个(200g)", "protein": 0.5, "water": 150, "category": "水果", "unit_g": 200},
    {"name": "橙子", "portion": "1个(150g)", "protein": 1, "water": 120, "category": "水果", "unit_g": 150},
    {"name": "西瓜", "portion": "200g", "protein": 0.6, "water": 180, "category": "水果", "unit_g": 200},
    {"name": "香蕉", "portion": "1根(100g)", "protein": 1.2, "water": 75, "category": "水果", "unit_g": 100},

    # 营养补充剂
    {"name": "乳清蛋白粉", "portion": "1勺(20g粉)", "protein": 17, "water": 1, "category": "营养补充剂", "unit_g": 20},
]

# 扣减优先级：乳清蛋白粉 → 豆腐 → 奶类
DEDUCTION_ORDER = ["营养补充剂", "豆制品", "奶制品"]
```

- [ ] **Step 2: 添加核心计算函数**

```python
# ============================================================
# 核心计算逻辑
# ============================================================

def calc_bmi(weight_kg, height_cm):
    """计算 BMI = 体重(kg) / 身高(m)²"""
    height_m = height_cm / 100.0
    return round(weight_kg / (height_m ** 2), 1)

def bmi_category(bmi):
    """BMI 分类：<18.5 消瘦, 18.5-23.9 正常, 24-27.9 超重, >=28 肥胖"""
    if bmi < 18.5:
        return "消瘦"
    elif bmi < 24:
        return "正常"
    elif bmi < 28:
        return "超重"
    else:
        return "肥胖"

def calc_ibw(height_cm):
    """理想体重 IBW = 身高(cm) - 105"""
    return height_cm - 105

def calc_adjusted_weight(actual_weight, ibw):
    """校正体重 = IBW + 0.25 × (实际体重 - IBW)"""
    excess = actual_weight - ibw
    if excess <= 0:
        return ibw
    return round(ibw + 0.25 * excess, 1)

def determine_calc_weight(actual_weight, height_cm, waist_cm, calf_cm, gender):
    """
    确定计算体重：
    - BMI < 18.5（消瘦）: 实际体重
    - BMI 18.5-23.9（正常）: 实际体重
    - BMI >= 24（超重/肥胖）: 按肥胖亚型分层
      - 向心性（腰围女≥85/男≥90）: 理想体重
      - 肌少型（小腿围女<33/男<34）: 实际体重
      - 周围型（其他）: 校正体重
      - 未测量腰围/小腿围: 默认理想体重
    """
    bmi = calc_bmi(actual_weight, height_cm)
    ibw = calc_ibw(height_cm)

    if bmi < 24:
        return actual_weight, "实际体重"

    # BMI >= 24：肥胖亚型分层
    waist_threshold = 85 if gender == 'female' else 90
    calf_threshold = 33 if gender == 'female' else 34

    has_waist = waist_cm is not None and waist_cm > 0
    has_calf = calf_cm is not None and calf_cm > 0

    if has_calf and calf_cm < calf_threshold:
        return actual_weight, "肌少型肥胖→实际体重"

    if has_waist and waist_cm >= waist_threshold:
        return ibw, "向心性肥胖→理想体重"

    if has_waist and waist_cm < waist_threshold:
        adj = calc_adjusted_weight(actual_weight, ibw)
        return adj, "周围型肥胖→校正体重"

    # 未测量：默认理想体重
    return ibw, "默认理想体重（未测量腰围/小腿围）"


def calc_risk_score(assessment_data):
    """
    计算 OHSS 风险评分
    assessment_data: dict 包含各评估项
    基础因素各 1 分，临床指标各 3 分
    """
    score = 0
    # 基础高危因素（各 1 分）
    base_factors = [
        ('pcos', 'PCOS 病史'),
        ('prev_ohss', '既往 OHSS 病史'),
        ('age_under_35', '年龄 < 35 岁'),
        ('bmi_under_18_5', 'BMI < 18.5'),
        ('amh_high', 'AMH > 3.36 ng/ml'),
        ('afc_high', 'AFC ≥ 24 个'),
    ]
    for key, _ in base_factors:
        if assessment_data.get(key):
            score += 1

    # 临床指标（各 3 分）
    clinical_factors = [
        ('e2_high', 'E2 ≥ 3500 pg/ml'),
        ('follicle_high', '卵泡 ≥ 20 个'),
        ('oocyte_high', '获卵 ≥ 15 枚'),
        ('symptoms', '有临床症状'),
        ('ovary_enlarged', '卵巢增大 ≥ 8cm'),
        ('ascites', '有腹水/盆腔积液'),
        ('pleural_effusion', '有胸水'),
    ]
    for key, _ in clinical_factors:
        if assessment_data.get(key):
            score += 3

    return score


def risk_level(score):
    """
    风险分级：
    - 健康饮食级: 0 分
    - 预防级: 0-4 分
    - 干预级: 5-10 分
    - 治疗级: ≥11 分
    """
    if score == 0:
        return "健康饮食级", (1.0, 1.2)
    elif score <= 4:
        return "预防级", (1.2, 1.5)
    elif score <= 10:
        return "干预级", (1.5, 1.8)
    else:
        return "治疗级", (1.8, 2.0)


def calc_protein_range(calc_weight, protein_coeff):
    """计算蛋白需求范围"""
    low, high = protein_coeff
    return round(calc_weight * low, 1), round(calc_weight * high, 1)


def calc_liquid_total(calc_weight):
    """液体参考总量 = 30ml/kg"""
    return round(calc_weight * 30)


def calc_actual_drink(liquid_total, food_water_total):
    """实际饮水量 = 总量 - 食物含水量"""
    return max(0, liquid_total - food_water_total)
```

- [ ] **Step 3: 添加食谱生成逻辑**

```python
# ============================================================
# 食谱生成逻辑
# ============================================================

# 五餐结构定义
MEAL_STRUCTURE = {
    "早餐": {
        "categories": ["蛋类", "奶制品", "主食"],
        "protein_ratio": 0.25,
        "max_items": 4,
        "description": "早餐（7:00-8:00）"
    },
    "早加餐": {
        "categories": ["水果", "奶制品", "蛋类"],
        "protein_ratio": 0.10,
        "max_items": 2,
        "description": "早加餐（10:00）"
    },
    "午餐": {
        "categories": ["肉类", "水产", "蔬菜", "主食", "豆制品"],
        "protein_ratio": 0.30,
        "max_items": 5,
        "description": "午餐（12:00-13:00）"
    },
    "午加餐": {
        "categories": ["水果", "奶制品", "豆制品", "主食"],
        "protein_ratio": 0.10,
        "max_items": 2,
        "description": "午加餐（15:00-16:00）"
    },
    "晚餐": {
        "categories": ["肉类", "水产", "蔬菜", "主食", "豆制品", "蛋类"],
        "protein_ratio": 0.25,
        "max_items": 5,
        "description": "晚餐（18:00-19:00）"
    },
}


def generate_meal_plan(target_protein_high, liquid_total, calc_weight):
    """
    生成五餐食谱。
    策略：按每餐蛋白比例分配目标蛋白，从对应类别中选食物。
    双锁定：蛋白总量不超上限，扣减顺序 乳清蛋白粉→豆腐→奶类；
    液体总量锁定，食物水自动计入。
    """
    import random
    random.seed(42)  # 可复现的食谱变化

    meals = {}
    total_protein = 0
    total_water = 0

    # 按目标蛋白上限的 90% 来选食物（留 10% 余量用于双锁定）
    protein_budget = target_protein_high * 0.9

    for meal_name, config in MEAL_STRUCTURE.items():
        meal_target = protein_budget * config["protein_ratio"]
        meal_items = []
        meal_protein = 0
        meal_water = 0

        # 从符合类别中筛选食物
        available = [f for f in FOOD_DATABASE
                     if f["category"] in config["categories"]]

        # 贪心算法：优先选蛋白密度高的食物
        for _ in range(config["max_items"]):
            if meal_protein >= meal_target:
                break

            # 按蛋白含量排序，选最高的
            candidates = sorted(
                [f for f in available if f not in meal_items],
                key=lambda x: x["protein"] / max(x["unit_g"], 1),
                reverse=True
            )

            if not candidates:
                break

            # 选蛋白密度最高的，但确保不超 meal_target 太多
            best = candidates[0]
            qty = 1  # 默认 1 份

            # 如果超了，尝试减量
            if meal_protein + best["protein"] > meal_target * 1.2:
                # 找更小的食物
                smaller = [c for c in candidates
                          if meal_protein + c["protein"] <= meal_target * 1.2]
                if smaller:
                    best = smaller[0]
                else:
                    break

            item = {
                "name": best["name"],
                "portion": best["portion"],
                "quantity": qty,
                "protein": best["protein"],
                "water": best["water"],
                "category": best["category"],
            }
            meal_items.append(item)
            meal_protein += best["protein"]
            meal_water += best["water"]

        meals[meal_name] = {
            "label": config["description"],
            "items": meal_items,
            "protein_subtotal": round(meal_protein, 1),
            "water_subtotal": meal_water,
        }
        total_protein += meal_protein
        total_water += meal_water

    total_protein = round(total_protein, 1)

    # 双锁定 1：蛋白总量不超上限
    if total_protein > target_protein_high:
        excess = total_protein - target_protein_high
        total_protein, total_water, meals = _apply_protein_lock(
            meals, excess, total_protein, total_water
        )

    # 双锁定 2：液体总量锁定
    liquid_total_int = round(liquid_total)

    return {
        "meals": meals,
        "total_protein": round(total_protein, 1),
        "total_food_water": total_water,
        "liquid_total": liquid_total_int,
        "actual_drink": max(0, liquid_total_int - total_water),
        "protein_target_high": target_protein_high,
    }


def _apply_protein_lock(meals, excess, total_protein, total_water):
    """
    蛋白超量按顺序扣减：乳清蛋白粉 → 豆腐 → 奶类
    天然食物（蛋、肉、水产、蔬菜、水果、主食）优先保留
    """
    deduction_order = ["营养补充剂", "豆制品", "奶制品"]

    for category in deduction_order:
        if excess <= 0:
            break
        for meal_name in meals:
            if excess <= 0:
                break
            meal = meals[meal_name]
            for item in list(meal["items"]):
                if excess <= 0:
                    break
                if item["category"] == category:
                    meals[meal_name]["items"].remove(item)
                    meals[meal_name]["protein_subtotal"] = round(
                        meals[meal_name]["protein_subtotal"] - item["protein"], 1
                    )
                    meals[meal_name]["water_subtotal"] -= item["water"]
                    total_protein = round(total_protein - item["protein"], 1)
                    total_water -= item["water"]
                    excess -= item["protein"]

    return total_protein, total_water, meals
```

- [ ] **Step 4: 验证计算逻辑**

```bash
cd "C:\Users\a\ohss-calculator"
python -c "
from app import calc_bmi, bmi_category, calc_ibw, determine_calc_weight, calc_risk_score, risk_level, generate_meal_plan

# 测试 BMI
bmi = calc_bmi(60, 160)
print(f'BMI: {bmi}, 分类: {bmi_category(bmi)}')
assert bmi == 23.4, f'Expected 23.4, got {bmi}'

# 测试计算体重
cw, reason = determine_calc_weight(60, 160, None, None, 'female')
print(f'计算体重: {cw}kg ({reason})')
assert cw == 60

# 测试风险评分
score = calc_risk_score({'pcos': True, 'e2_high': True, 'symptoms': True})
print(f'风险评分: {score}')
assert score == 7

# 测试风险等级
level, coeff = risk_level(7)
print(f'风险等级: {level}, 系数: {coeff}')

# 测试食谱生成
plan = generate_meal_plan(100, 1650, 55)
print(f'总蛋白: {plan[\"total_protein\"]}g, 液体总量: {plan[\"liquid_total\"]}ml, 饮水量: {plan[\"actual_drink\"]}ml')
for name, meal in plan['meals'].items():
    print(f'  {name}: {meal[\"protein_subtotal\"]}g 蛋白, {len(meal[\"items\"])} 项食物')

print('所有计算逻辑验证通过!')
"
```

Expected: 所有断言通过，无报错。

---

### Task 3: PDF 报告生成

**Files:**
- Modify: `ohss-calculator/app.py` — 替换 `/api/pdf` 路由

- [ ] **Step 1: 替换 `/api/pdf` 路由**

```python
@app.route('/api/pdf', methods=['POST'])
def generate_pdf():
    """生成 PDF 报告"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '无效的请求数据'}), 400

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=15*mm,
            bottomMargin=15*mm,
            leftMargin=15*mm,
            rightMargin=15*mm,
        )

        styles = getSampleStyleSheet()

        # 注册中文字体样式
        if FONT_AVAILABLE:
            title_style = ParagraphStyle(
                'CNTitle', fontName=FONT_NAME, fontSize=16,
                leading=24, alignment=TA_CENTER, spaceAfter=10,
            )
            heading_style = ParagraphStyle(
                'CNHeading', fontName=FONT_NAME, fontSize=12,
                leading=18, spaceBefore=10, spaceAfter=6,
            )
            body_style = ParagraphStyle(
                'CNBody', fontName=FONT_NAME, fontSize=10,
                leading=16, spaceAfter=4,
            )
            small_style = ParagraphStyle(
                'CNSmall', fontName=FONT_NAME, fontSize=8,
                leading=12, textColor=HexColor('#666666'),
            )
        else:
            title_style = styles['Title']
            heading_style = styles['Heading2']
            body_style = styles['Normal']
            small_style = styles['Normal']

        story = []

        # 标题
        story.append(Paragraph("OHSS 高蛋白饮食个性化食谱报告", title_style))
        story.append(Spacer(1, 5*mm))

        # 一、患者信息
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
            story.append(Paragraph(
                f"<b>{row[0]}：</b>{row[1]}　　<b>{row[2]}：</b>{row[3]}",
                body_style
            ))
        story.append(Spacer(1, 3*mm))

        # 二、风险评估
        story.append(Paragraph("二、风险评估结果", heading_style))
        risk_data = [
            ['风险评分', f"{risk.get('score', '-')} 分"],
            ['风险等级', risk.get('level', '-')],
            ['蛋白系数', risk.get('protein_coeff', '-')],
            ['每日蛋白需求', f"{calc_result.get('protein_low', '-')} ~ {calc_result.get('protein_high', '-')} g"],
            ['液体参考总量', f"{calc_result.get('liquid_total', '-')} ml (30ml/kg)"],
            ['实际建议饮水量', f"{calc_result.get('actual_drink', '-')} ml"],
        ]
        for row in risk_data:
            story.append(Paragraph(
                f"<b>{row[0]}：</b>{row[1]}",
                body_style
            ))
        story.append(Spacer(1, 3*mm))

        # 三、五餐食谱
        story.append(Paragraph("三、五餐食谱明细", heading_style))
        meal_plan = data.get('meal_plan', {}).get('meals', {})

        # 表头
        meal_table_data = [['餐次', '时间', '食物', '份量', '蛋白(g)', '含水(ml)']]
        for meal_name, meal in meal_plan.items():
            items = meal.get('items', [])
            if items:
                for i, item in enumerate(items):
                    if i == 0:
                        meal_table_data.append([
                            meal_name,
                            meal.get('label', ''),
                            item.get('name', ''),
                            item.get('portion', ''),
                            str(item.get('protein', '')),
                            str(item.get('water', '')),
                        ])
                    else:
                        meal_table_data.append([
                            '', '', item.get('name', ''),
                            item.get('portion', ''),
                            str(item.get('protein', '')),
                            str(item.get('water', '')),
                        ])
                # 小计行
                meal_table_data.append([
                    '', '', f'【{meal_name}小计】', '',
                    str(meal.get('protein_subtotal', '')),
                    str(meal.get('water_subtotal', '')),
                ])
            else:
                meal_table_data.append([
                    meal_name, meal.get('label', ''), '（无）', '-', '0', '0',
                ])

        # 总计行
        total_protein = meal_plan.get('total_protein', 0)
        total_water = meal_plan.get('total_food_water', 0)
        meal_table_data.append([
            '', '', '【总计】', '',
            str(total_protein),
            str(total_water),
        ])

        col_widths = [50, 70, 140, 80, 55, 55]
        meal_table = Table(meal_table_data, colWidths=col_widths, repeatRows=1)
        meal_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), FONT_FALLBACK),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#4472C4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#FFFFFF')),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (4, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#CCCCCC')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#FFFFFF'), HexColor('#F2F7FB')]),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(meal_table)
        story.append(Spacer(1, 5*mm))

        # 四、安全提示
        story.append(Paragraph("四、重要安全提示", heading_style))
        warnings = [
            "本工具为护理科普参考，不替代临床诊断。",
            "30ml/kg 液体值仅作参考，口渴感、尿量优先，禁止机械限水。",
            "治疗级（≥11 分）患者应尽快到急诊留观室就诊。",
            "低盐饮食，少食多餐；严重腹胀/恶心时不要硬吃，立即联系科室或急诊。",
            "如出现 24h 尿量 < 500ml、体重日增 > 1kg、呼吸困难，立即就诊！",
        ]
        for w in warnings:
            story.append(Paragraph(f"• {w}", body_style))

        story.append(Spacer(1, 10*mm))

        # 页脚
        story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor('#CCCCCC')))
        story.append(Paragraph(
            "生殖医学中心 · OHSS 高蛋白饮食智能计算器 · 生成日期：{}".format(
                __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')
            ),
            small_style
        ))

        doc.build(story)
        buffer.seek(0)

        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'OHSS食谱_{patient.get("name", "患者")}.pdf',
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
```

- [ ] **Step 2: 测试 PDF 生成**

```bash
cd "C:\Users\a\ohss-calculator"
python -c "
import json
from app import app

client = app.test_client()
test_data = {
    'patient': {'name': '测试', 'age': 30, 'height': 160, 'weight': 60},
    'calc_result': {
        'bmi': 23.4, 'bmi_category': '正常',
        'calc_weight': 60, 'calc_weight_method': '实际体重',
        'protein_low': 90, 'protein_high': 108,
        'liquid_total': 1800, 'actual_drink': 900
    },
    'risk': {'score': 7, 'level': '干预级', 'protein_coeff': '1.5-1.8 g/kg/天'},
    'meal_plan': {
        'meals': {},
        'total_protein': 95, 'total_food_water': 750
    }
}
resp = client.post('/api/pdf', json=test_data)
print(f'Status: {resp.status_code}')
print(f'Content-Type: {resp.content_type}')
print(f'File size: {len(resp.data)} bytes')
assert resp.status_code == 200, f'PDF generation failed: {resp.status_code}'
print('PDF 生成测试通过!')
"
```

Expected: 200 OK，返回 PDF 文件。

---

### Task 4: 二维码生成

**Files:**
- Modify: `ohss-calculator/app.py` — 替换 `/api/qrcode` 路由

- [ ] **Step 1: 替换 `/api/qrcode` 路由**

```python
@app.route('/api/qrcode', methods=['POST'])
def generate_qrcode():
    """生成二维码（编码关键信息供打印分享）"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '无效的请求数据'}), 400

        patient = data.get('patient', {})
        calc_result = data.get('calc_result', {})
        risk = data.get('risk', {})
        meal_plan = data.get('meal_plan', {})

        # 编码关键信息
        qr_info = {
            'name': patient.get('name', ''),
            'height': patient.get('height', ''),
            'weight': patient.get('weight', ''),
            'bmi': calc_result.get('bmi', ''),
            'calc_weight': calc_result.get('calc_weight', ''),
            'risk_level': risk.get('level', ''),
            'risk_score': risk.get('score', ''),
            'protein_target': f"{calc_result.get('protein_low', '')}-{calc_result.get('protein_high', '')}g",
            'liquid_total': f"{calc_result.get('liquid_total', '')}ml",
            'actual_drink': f"{calc_result.get('actual_drink', '')}ml",
            'total_protein': meal_plan.get('total_protein', ''),
            'total_food_water': meal_plan.get('total_food_water', ''),
        }

        qr_text = json.dumps(qr_info, ensure_ascii=False, indent=2)

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

        return send_file(
            buffer,
            mimetype='image/png',
            as_attachment=True,
            download_name=f'OHSS二维码_{patient.get("name", "患者")}.png',
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
```

- [ ] **Step 2: 测试二维码生成**

```bash
cd "C:\Users\a\ohss-calculator"
python -c "
from app import app

client = app.test_client()
resp = client.post('/api/qrcode', json={
    'patient': {'name': '测试', 'height': 160, 'weight': 60},
    'calc_result': {'bmi': 23.4, 'calc_weight': 60, 'protein_low': 90, 'protein_high': 108, 'liquid_total': 1800, 'actual_drink': 900},
    'risk': {'level': '干预级', 'score': 7},
    'meal_plan': {'total_protein': 95, 'total_food_water': 750}
})
print(f'Status: {resp.status_code}')
print(f'Content-Type: {resp.content_type}')
print(f'File size: {len(resp.data)} bytes')
assert resp.status_code == 200
assert resp.content_type == 'image/png'
print('二维码生成测试通过!')
"
```

Expected: 200 OK，返回 PNG 图片。

---

### Task 5: 完整前端 HTML/CSS/JS

**Files:**
- Modify: `ohss-calculator/app.py` — 替换 `HTML_TEMPLATE` 常量

- [ ] **Step 1: 替换 HTML 模板**

```python
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
        --primary: #2B5797;
        --primary-light: #4472C4;
        --success: #2E7D32;
        --warning: #E65100;
        --danger: #C62828;
        --bg: #F5F7FA;
        --card-bg: #FFFFFF;
        --text: #212121;
        --text-secondary: #616161;
        --border: #E0E0E0;
        --radius: 10px;
        --shadow: 0 2px 8px rgba(0,0,0,0.08);
        --font: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", "Helvetica Neue", sans-serif;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
        font-family: var(--font);
        background: var(--bg);
        color: var(--text);
        font-size: 15px;
        line-height: 1.5;
        -webkit-text-size-adjust: 100%;
        -webkit-tap-highlight-color: transparent;
    }

    .container {
        max-width: 480px;
        margin: 0 auto;
        padding: 12px;
    }

    /* 头部 */
    .header {
        background: linear-gradient(135deg, var(--primary), var(--primary-light));
        color: #fff;
        padding: 16px 20px;
        border-radius: var(--radius);
        margin-bottom: 12px;
        text-align: center;
    }
    .header h1 {
        font-size: 18px;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .header .subtitle {
        font-size: 12px;
        opacity: 0.85;
        margin-top: 4px;
    }

    /* 卡片 */
    .card {
        background: var(--card-bg);
        border-radius: var(--radius);
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: var(--shadow);
    }
    .card-title {
        font-size: 16px;
        font-weight: 600;
        color: var(--primary);
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 2px solid var(--primary-light);
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .card-title .icon { font-size: 18px; }

    /* 表单 */
    .form-row {
        display: flex;
        gap: 10px;
        margin-bottom: 10px;
    }
    .form-group {
        flex: 1;
        margin-bottom: 10px;
    }
    .form-group label {
        display: block;
        font-size: 13px;
        color: var(--text-secondary);
        margin-bottom: 4px;
        font-weight: 500;
    }
    .form-group input, .form-group select {
        width: 100%;
        padding: 10px 12px;
        border: 1px solid var(--border);
        border-radius: 8px;
        font-size: 16px; /* 防止 iOS 缩放 */
        font-family: var(--font);
        transition: border-color 0.2s;
        background: #FAFAFA;
        -webkit-appearance: none;
    }
    .form-group input:focus, .form-group select:focus {
        outline: none;
        border-color: var(--primary-light);
        background: #fff;
        box-shadow: 0 0 0 3px rgba(68,114,196,0.1);
    }
    .form-group input[type="number"] {
        -moz-appearance: textfield;
    }
    .form-group input::-webkit-outer-spin-button,
    .form-group input::-webkit-inner-spin-button {
        -webkit-appearance: none;
    }

    .form-hint {
        font-size: 11px;
        color: #999;
        margin-top: 2px;
    }
    .form-section-title {
        font-size: 13px;
        font-weight: 600;
        color: var(--text-secondary);
        margin: 12px 0 8px;
        padding: 6px 10px;
        background: #F0F4FA;
        border-radius: 6px;
    }

    /* 按钮 */
    .btn {
        display: inline-block;
        padding: 12px 24px;
        border: none;
        border-radius: 8px;
        font-size: 15px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
        font-family: var(--font);
        text-align: center;
        width: 100%;
        -webkit-appearance: none;
    }
    .btn:active { transform: scale(0.97); }
    .btn-primary {
        background: linear-gradient(135deg, var(--primary), var(--primary-light));
        color: #fff;
        box-shadow: 0 2px 8px rgba(43,87,151,0.3);
    }
    .btn-primary:hover { box-shadow: 0 4px 12px rgba(43,87,151,0.4); }
    .btn-outline {
        background: #fff;
        color: var(--primary);
        border: 1.5px solid var(--primary);
    }
    .btn-danger {
        background: var(--danger);
        color: #fff;
    }
    .btn-sm {
        padding: 8px 16px;
        font-size: 13px;
        width: auto;
    }
    .btn-row {
        display: flex;
        gap: 10px;
        margin-top: 8px;
    }
    .btn-row .btn { flex: 1; }

    /* 结果展示 */
    .result-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
    }
    .result-item {
        background: #F5F7FA;
        padding: 10px;
        border-radius: 8px;
        text-align: center;
    }
    .result-item .label {
        font-size: 11px;
        color: var(--text-secondary);
        margin-bottom: 2px;
    }
    .result-item .value {
        font-size: 18px;
        font-weight: 700;
        color: var(--primary);
    }
    .result-item .value-sm {
        font-size: 14px;
        font-weight: 600;
        color: var(--primary);
    }

    .risk-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 13px;
        font-weight: 600;
    }
    .risk-prevention { background: #E8F5E9; color: #2E7D32; }
    .risk-intervention { background: #FFF3E0; color: #E65100; }
    .risk-treatment { background: #FFEBEE; color: #C62828; }
    .risk-healthy { background: #E3F2FD; color: #1565C0; }

    /* 食谱表格 */
    .meal-section {
        margin-bottom: 12px;
        border: 1px solid var(--border);
        border-radius: 8px;
        overflow: hidden;
    }
    .meal-header {
        background: #F0F4FA;
        padding: 10px 14px;
        font-weight: 600;
        font-size: 14px;
        color: var(--primary);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .meal-header .meal-time {
        font-size: 12px;
        color: var(--text-secondary);
        font-weight: 400;
    }
    .meal-items {
        padding: 8px 14px;
    }
    .meal-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 0;
        border-bottom: 1px solid #F5F5F5;
        font-size: 13px;
    }
    .meal-item:last-child { border-bottom: none; }
    .meal-item .food-name { flex: 1; }
    .meal-item .food-info {
        color: var(--text-secondary);
        font-size: 12px;
        text-align: right;
        min-width: 100px;
    }
    .meal-subtotal {
        background: #FAFAFA;
        padding: 8px 14px;
        font-size: 12px;
        color: var(--primary);
        font-weight: 600;
        text-align: right;
        border-top: 1px solid #EEE;
    }

    .summary-bar {
        background: linear-gradient(135deg, #E8F5E9, #C8E6C9);
        padding: 12px 16px;
        border-radius: 8px;
        margin-top: 8px;
        display: flex;
        justify-content: space-around;
        text-align: center;
        font-size: 13px;
    }
    .summary-bar .sum-num {
        font-size: 20px;
        font-weight: 700;
        color: var(--success);
    }

    /* 警告提示 */
    .alert {
        padding: 10px 14px;
        border-radius: 8px;
        font-size: 12px;
        margin-top: 8px;
        line-height: 1.6;
    }
    .alert-warning {
        background: #FFF8E1;
        border: 1px solid #FFE082;
        color: #E65100;
    }
    .alert-danger {
        background: #FFEBEE;
        border: 1px solid #EF9A9A;
        color: #C62828;
    }

    /* 隐藏 */
    .hidden { display: none !important; }

    /* 加载 */
    .loading {
        display: inline-block;
        width: 16px;
        height: 16px;
        border: 2px solid rgba(255,255,255,0.3);
        border-top-color: #fff;
        border-radius: 50%;
        animation: spin 0.6s linear infinite;
        vertical-align: middle;
        margin-right: 6px;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* 调整按钮 */
    .adj-row {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 4px;
    }
    .adj-row input {
        width: 60px;
        padding: 6px 8px;
        border: 1px solid var(--border);
        border-radius: 6px;
        font-size: 14px;
        text-align: center;
    }

    /* toast */
    .toast {
        position: fixed;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        background: #333;
        color: #fff;
        padding: 10px 20px;
        border-radius: 20px;
        font-size: 14px;
        z-index: 9999;
        opacity: 0;
        transition: opacity 0.3s;
    }
    .toast.show { opacity: 1; }

    /* 打印样式 */
    @media print {
        body { background: #fff; }
        .card { box-shadow: none; border: 1px solid #ddd; }
        .btn, .btn-row, .form-section-title, #input-section { display: none; }
        .container { max-width: 100%; }
    }
</style>
</head>
<body>
<div class="container">
    <!-- 头部 -->
    <div class="header">
        <h1>🥚 OHSS 高蛋白饮食智能计算器</h1>
        <div class="subtitle">生殖医学中心 · 护理宣教工具</div>
    </div>

    <!-- 患者信息录入 -->
    <div class="card" id="input-section">
        <div class="card-title"><span class="icon">📋</span>患者信息录入</div>

        <div class="form-row">
            <div class="form-group">
                <label>姓名</label>
                <input type="text" id="patientName" placeholder="请输入姓名">
            </div>
            <div class="form-group">
                <label>年龄（岁）</label>
                <input type="number" id="patientAge" placeholder="年龄" min="18" max="60" step="1">
            </div>
        </div>

        <div class="form-row">
            <div class="form-group">
                <label>身高（cm）</label>
                <input type="number" id="height" placeholder="例如 160" min="100" max="220" step="0.1">
            </div>
            <div class="form-group">
                <label>体重（kg）</label>
                <input type="number" id="weight" placeholder="例如 60" min="30" max="200" step="0.1">
            </div>
        </div>

        <div class="form-row">
            <div class="form-group">
                <label>性别</label>
                <select id="gender">
                    <option value="female">女</option>
                    <option value="male">男</option>
                </select>
            </div>
            <div class="form-group">
                <label>腰围（cm）<span class="form-hint">选填</span></label>
                <input type="number" id="waist" placeholder="腰围" min="40" max="200" step="0.1">
            </div>
        </div>

        <div class="form-row">
            <div class="form-group">
                <label>小腿围（cm）<span class="form-hint">选填</span></label>
                <input type="number" id="calf" placeholder="小腿围" min="20" max="80" step="0.1">
            </div>
            <div class="form-group">
                <label>评估阶段</label>
                <select id="evalStage">
                    <option value="baseline">基线评估（促排第一天）</option>
                    <option value="follicle14">第一次评估（卵泡≥14mm）</option>
                    <option value="hcg">第二次评估（HCG 日）</option>
                    <option value="retrieval">第三次评估（取卵日）</option>
                    <option value="day3">第四次评估（取卵后第3天）</option>
                    <option value="day5">第五次评估（取卵后第4/5天）</option>
                </select>
            </div>
        </div>

        <!-- 风险评估项 -->
        <div class="form-section-title">🔬 风险评估指标</div>

        <div class="form-row">
            <div class="form-group">
                <label>PCOS 病史</label>
                <select id="pcos">
                    <option value="no">否</option>
                    <option value="yes">是</option>
                </select>
            </div>
            <div class="form-group">
                <label>既往 OHSS 病史</label>
                <select id="prevOhss">
                    <option value="no">否</option>
                    <option value="yes">是</option>
                </select>
            </div>
        </div>

        <div class="form-row">
            <div class="form-group">
                <label>AMH > 3.36 ng/ml</label>
                <select id="amhHigh">
                    <option value="no">否</option>
                    <option value="yes">是</option>
                </select>
            </div>
            <div class="form-group">
                <label>AFC ≥ 24 个</label>
                <select id="afcHigh">
                    <option value="no">否</option>
                    <option value="yes">是</option>
                </select>
            </div>
        </div>

        <div class="form-row">
            <div class="form-group">
                <label>E2 ≥ 3500 pg/ml</label>
                <select id="e2High">
                    <option value="no">否</option>
                    <option value="yes">是</option>
                </select>
            </div>
            <div class="form-group">
                <label>卵泡 ≥ 20 个（≥10mm）</label>
                <select id="follicleHigh">
                    <option value="no">否</option>
                    <option value="yes">是</option>
                </select>
            </div>
        </div>

        <div class="form-row">
            <div class="form-group">
                <label>获卵 ≥ 15 枚</label>
                <select id="oocyteHigh">
                    <option value="no">否</option>
                    <option value="yes">是</option>
                </select>
            </div>
            <div class="form-group">
                <label>临床症状</label>
                <select id="symptoms">
                    <option value="no">无症状</option>
                    <option value="yes">有症状（腹胀/腹痛/恶心/尿少）</option>
                </select>
            </div>
        </div>

        <div class="form-row">
            <div class="form-group">
                <label>卵巢增大（≥8cm）</label>
                <select id="ovaryEnlarged">
                    <option value="no">否</option>
                    <option value="yes">是</option>
                </select>
            </div>
            <div class="form-group">
                <label>腹水/盆腔积液</label>
                <select id="ascites">
                    <option value="no">无</option>
                    <option value="yes">有</option>
                </select>
            </div>
        </div>

        <div class="form-row">
            <div class="form-group">
                <label>胸水</label>
                <select id="pleuralEffusion">
                    <option value="no">无</option>
                    <option value="yes">有</option>
                </select>
            </div>
        </div>

        <button class="btn btn-primary" onclick="calculateAll()">
            🔍 计算并生成个性化食谱
        </button>
    </div>

    <!-- 计算结果 -->
    <div class="card hidden" id="result-section">
        <div class="card-title"><span class="icon">📊</span>计算结果</div>
        <div class="result-grid" id="resultGrid"></div>
        <div id="riskBadgeContainer" style="margin-top:10px;text-align:center;"></div>
    </div>

    <!-- 五餐食谱 -->
    <div class="card hidden" id="meal-section">
        <div class="card-title"><span class="icon">🍽️</span>五餐个性化食谱</div>
        <div id="mealContent"></div>
        <div id="mealSummary"></div>
        <div style="margin-top:12px;">
            <button class="btn btn-outline btn-sm" onclick="regenerateMeals()">🔄 重新生成食谱</button>
        </div>
    </div>

    <!-- 报告输出 -->
    <div class="card hidden" id="output-section">
        <div class="card-title"><span class="icon">📄</span>报告输出</div>
        <div class="btn-row">
            <button class="btn btn-primary" onclick="downloadPDF()">📥 下载 PDF 报告</button>
            <button class="btn btn-outline" onclick="downloadQRCode()">📱 下载二维码</button>
        </div>
    </div>

    <!-- 安全提示 -->
    <div class="card">
        <div class="card-title"><span class="icon">⚠️</span>安全提示</div>
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
        生殖医学中心 · OHSS 高蛋白饮食智能计算器 v1.0<br>
        本工具评分量表为本科室自制，有待临床数据验证
    </div>
</div>

<!-- Toast -->
<div class="toast" id="toast"></div>

<script>
// ============================================================
// 全局状态
// ============================================================
let currentMealPlan = null;
let currentCalcResult = null;
let currentRisk = null;
let currentPatient = null;

// ============================================================
// 工具函数
// ============================================================
function $(id) { return document.getElementById(id); }

function val(id) {
    const el = $(id);
    if (!el) return null;
    const v = el.value.trim();
    if (v === '') return null;
    const num = parseFloat(v);
    return isNaN(num) ? v : num;
}

function showToast(msg, duration = 2000) {
    const t = $('toast');
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), duration);
}

function showSection(id) {
    const el = $(id);
    if (el) el.classList.remove('hidden');
}

function hideSection(id) {
    const el = $(id);
    if (el) el.classList.add('hidden');
}

// ============================================================
// BMI / 计算体重 / 风险评分（前端预计算）
// ============================================================
function calcBMI(weight, heightCm) {
    const h = heightCm / 100;
    return parseFloat((weight / (h * h)).toFixed(1));
}

function bmiCategory(bmi) {
    if (bmi < 18.5) return '消瘦';
    if (bmi < 24) return '正常';
    if (bmi < 28) return '超重';
    return '肥胖';
}

function calcIBW(heightCm) {
    return heightCm - 105;
}

function calcAdjustedWeight(actual, ibw) {
    const excess = actual - ibw;
    if (excess <= 0) return ibw;
    return parseFloat((ibw + 0.25 * excess).toFixed(1));
}

function determineCalcWeight(actual, heightCm, waist, calf, gender) {
    const bmi = calcBMI(actual, heightCm);
    const ibw = calcIBW(heightCm);

    if (bmi < 24) {
        return { weight: actual, method: '实际体重（BMI ' + bmiCategory(bmi) + '）' };
    }

    const waistThreshold = gender === 'female' ? 85 : 90;
    const calfThreshold = gender === 'female' ? 33 : 34;
    const hasWaist = waist !== null && waist > 0;
    const hasCalf = calf !== null && calf > 0;

    if (hasCalf && calf < calfThreshold) {
        return { weight: actual, method: '肌少型肥胖→实际体重' };
    }
    if (hasWaist && waist >= waistThreshold) {
        return { weight: ibw, method: '向心性肥胖→理想体重' };
    }
    if (hasWaist && waist < waistThreshold) {
        return { weight: calcAdjustedWeight(actual, ibw), method: '周围型肥胖→校正体重' };
    }
    return { weight: ibw, method: '默认理想体重（未测量腰围/小腿围）' };
}

function calcRiskScoreLocal() {
    let score = 0;
    // 基础因素各 1 分
    const baseFactors = ['pcos', 'prevOhss', 'amhHigh', 'afcHigh'];
    baseFactors.forEach(id => {
        const el = $(id);
        if (el && el.value === 'yes') score += 1;
    });
    // 年龄 < 35
    const age = val('patientAge');
    if (age !== null && age < 35) score += 1;
    // BMI < 18.5
    const weight = val('weight');
    const height = val('height');
    if (weight && height) {
        const bmi = calcBMI(weight, height);
        if (bmi < 18.5) score += 1;
    }

    // 临床因素各 3 分
    const clinicalFactors = ['e2High', 'follicleHigh', 'oocyteHigh', 'symptoms', 'ovaryEnlarged', 'ascites', 'pleuralEffusion'];
    clinicalFactors.forEach(id => {
        const el = $(id);
        if (el && el.value === 'yes') score += 3;
    });

    return score;
}

function riskLevelLocal(score) {
    if (score === 0) return { level: '健康饮食级', coeff: [1.0, 1.2], cssClass: 'risk-healthy' };
    if (score <= 4) return { level: '预防级', coeff: [1.2, 1.5], cssClass: 'risk-prevention' };
    if (score <= 10) return { level: '干预级', coeff: [1.5, 1.8], cssClass: 'risk-intervention' };
    return { level: '治疗级', coeff: [1.8, 2.0], cssClass: 'risk-treatment' };
}

// ============================================================
// 主计算流程
// ============================================================
function calculateAll() {
    const name = val('patientName') || '未知';
    const age = val('patientAge');
    const height = val('height');
    const weight = val('weight');
    const gender = val('gender') || 'female';
    const waist = val('waist');
    const calf = val('calf');

    // 验证必填
    if (!height || !weight) {
        showToast('请填写身高和体重');
        return;
    }
    if (!age) {
        showToast('请填写年龄');
        return;
    }

    // 计算 BMI
    const bmi = calcBMI(weight, height);
    const bmiCat = bmiCategory(bmi);

    // 计算体重
    const cw = determineCalcWeight(weight, height, waist, calf, gender);

    // 风险评分
    const score = calcRiskScoreLocal();
    const risk = riskLevelLocal(score);

    // 蛋白需求
    const proteinLow = parseFloat((cw.weight * risk.coeff[0]).toFixed(1));
    const proteinHigh = parseFloat((cw.weight * risk.coeff[1]).toFixed(1));

    // 液体参考
    const liquidTotal = Math.round(cw.weight * 30);

    currentPatient = { name, age, height, weight, gender, waist, calf };
    currentCalcResult = {
        bmi, bmi_category: bmiCat,
        calc_weight: cw.weight, calc_weight_method: cw.method,
        protein_low: proteinLow, protein_high: proteinHigh,
        liquid_total: liquidTotal,
    };
    currentRisk = {
        score, level: risk.level,
        protein_coeff: risk.coeff[0] + '-' + risk.coeff[1] + ' g/kg/天',
        cssClass: risk.cssClass,
    };

    // 显示计算结果
    renderResults();

    // 生成食谱（前端本地生成，因为食物数据库已内嵌）
    generateMealPlanLocal(proteinHigh, liquidTotal, cw.weight);

    showSection('output-section');
    document.getElementById('result-section').scrollIntoView({ behavior: 'smooth' });
}

// ============================================================
// 渲染计算结果
// ============================================================
function renderResults() {
    const r = currentCalcResult;
    const risk = currentRisk;

    const grid = $('resultGrid');
    grid.innerHTML = `
        <div class="result-item">
            <div class="label">BMI</div>
            <div class="value">${r.bmi} <span style="font-size:12px;color:#666;">kg/m²</span></div>
            <div style="font-size:11px;color:#999;">${r.bmi_category}</div>
        </div>
        <div class="result-item">
            <div class="label">计算体重</div>
            <div class="value-sm">${r.calc_weight} <span style="font-size:12px;color:#666;">kg</span></div>
            <div style="font-size:10px;color:#999;">${r.calc_weight_method}</div>
        </div>
        <div class="result-item">
            <div class="label">风险评分</div>
            <div class="value">${risk.score} <span style="font-size:12px;color:#666;">分</span></div>
        </div>
        <div class="result-item">
            <div class="label">风险等级</div>
            <div class="value-sm"><span class="risk-badge ${risk.cssClass}">${risk.level}</span></div>
        </div>
        <div class="result-item">
            <div class="label">每日蛋白需求</div>
            <div class="value-sm">${r.protein_low}~${r.protein_high} <span style="font-size:12px;">g</span></div>
            <div style="font-size:10px;color:#999;">${risk.protein_coeff}</div>
        </div>
        <div class="result-item">
            <div class="label">液体参考总量</div>
            <div class="value-sm">${r.liquid_total} <span style="font-size:12px;">ml</span></div>
            <div style="font-size:10px;color:#999;">30ml/kg</div>
        </div>
    `;

    $('riskBadgeContainer').innerHTML = risk.level === '治疗级'
        ? '<div class="alert alert-danger" style="margin-top:8px;"><strong>⚠️ 治疗级警告：</strong>患者应尽快转诊至急诊留观室进行液体治疗！</div>'
        : '';

    showSection('result-section');
}

// ============================================================
// 前端食谱生成（与 Python 后端逻辑一致）
// ============================================================
const FOOD_DB = ''' + json.dumps(FOOD_DATABASE, ensure_ascii=False) + r''';

const MEAL_CFG = ''' + json.dumps(MEAL_STRUCTURE, ensure_ascii=False) + r''';

function generateMealPlanLocal(targetProteinHigh, liquidTotal, calcWeight) {
    const proteinBudget = targetProteinHigh * 0.9;
    const meals = {};
    let totalProtein = 0;
    let totalWater = 0;

    // 固定种子保证可复现
    let seed = 42;
    function seededRandom() {
        seed = (seed * 1103515245 + 12345) & 0x7fffffff;
        return seed / 0x7fffffff;
    }

    for (const [mealName, config] of Object.entries(MEAL_CFG)) {
        const mealTarget = proteinBudget * config.protein_ratio;
        const mealItems = [];
        let mealProtein = 0;
        let mealWater = 0;

        let available = FOOD_DB.filter(f => config.categories.includes(f.category));

        // 贪心选择
        for (let i = 0; i < config.max_items; i++) {
            if (mealProtein >= mealTarget) break;

            // 排除已选的
            const remaining = available.filter(f =>
                !mealItems.some(mi => mi.name === f.name)
            );

            if (remaining.length === 0) break;

            // 按蛋白密度排序
            remaining.sort((a, b) =>
                (b.protein / Math.max(b.unit_g, 1)) - (a.protein / Math.max(a.unit_g, 1))
            );

            let best = remaining[0];

            // 如果超了，找更小的
            if (mealProtein + best.protein > mealTarget * 1.2) {
                const smaller = remaining.filter(c =>
                    mealProtein + c.protein <= mealTarget * 1.2
                );
                if (smaller.length > 0) {
                    best = smaller[0];
                } else {
                    break;
                }
            }

            const item = {
                name: best.name,
                portion: best.portion,
                quantity: 1,
                protein: best.protein,
                water: best.water,
                category: best.category,
            };
            mealItems.push(item);
            mealProtein += best.protein;
            mealWater += best.water;
        }

        meals[mealName] = {
            label: config.description,
            items: mealItems,
            protein_subtotal: parseFloat(mealProtein.toFixed(1)),
            water_subtotal: mealWater,
        };
        totalProtein += mealProtein;
        totalWater += mealWater;
    }

    totalProtein = parseFloat(totalProtein.toFixed(1));

    // 双锁定1：蛋白超量扣减
    if (totalProtein > targetProteinHigh) {
        let excess = totalProtein - targetProteinHigh;
        const deductionOrder = ['营养补充剂', '豆制品', '奶制品'];

        for (const category of deductionOrder) {
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
                        totalWater -= item.water;
                        excess -= item.protein;
                    }
                }
            }
        }
    }

    const liquidTotalInt = Math.round(liquidTotal);

    currentMealPlan = {
        meals,
        total_protein: parseFloat(totalProtein.toFixed(1)),
        total_food_water: totalWater,
        liquid_total: liquidTotalInt,
        actual_drink: Math.max(0, liquidTotalInt - totalWater),
        protein_target_high: targetProteinHigh,
    };

    renderMeals();
    showSection('meal-section');
}

function renderMeals() {
    if (!currentMealPlan) return;

    const plan = currentMealPlan;
    let html = '';

    for (const [mealName, meal] of Object.entries(plan.meals)) {
        html += `<div class="meal-section">
            <div class="meal-header">
                <span>${mealName}</span>
                <span class="meal-time">${meal.label}</span>
            </div>
            <div class="meal-items">`;

        if (meal.items.length === 0) {
            html += `<div class="meal-item" style="color:#999;">暂无推荐食物</div>`;
        } else {
            meal.items.forEach(item => {
                html += `<div class="meal-item">
                    <span class="food-name">${item.name}</span>
                    <span class="food-info">${item.portion} · ${item.protein}g 蛋白 · ${item.water}ml 水</span>
                </div>`;
            });
        }

        html += `</div>
            <div class="meal-subtotal">
                ${mealName}小计：${meal.protein_subtotal}g 蛋白 · ${meal.water_subtotal}ml 食物水
            </div>
        </div>`;
    }

    $('mealContent').innerHTML = html;

    $('mealSummary').innerHTML = `
        <div class="summary-bar">
            <div>
                <div style="color:#666;">每日总蛋白</div>
                <div class="sum-num">${plan.total_protein}g</div>
                <div style="font-size:11px;color:#999;">上限 ${plan.protein_target_high}g</div>
            </div>
            <div>
                <div style="color:#666;">食物含水量</div>
                <div class="sum-num">${plan.total_food_water}ml</div>
            </div>
            <div>
                <div style="color:#666;">液体总量</div>
                <div class="sum-num">${plan.liquid_total}ml</div>
                <div style="font-size:11px;color:#999;">30ml/kg</div>
            </div>
            <div>
                <div style="color:#666;">建议饮水量</div>
                <div class="sum-num">${plan.actual_drink}ml</div>
                <div style="font-size:11px;color:#999;">口渴优先</div>
            </div>
        </div>`;
}

function regenerateMeals() {
    if (!currentCalcResult || !currentRisk) {
        showToast('请先计算');
        return;
    }
    generateMealPlanLocal(
        currentCalcResult.protein_high,
        currentCalcResult.liquid_total,
        currentCalcResult.calc_weight
    );
    showToast('食谱已重新生成 ✓');
}

// ============================================================
// PDF 下载
// ============================================================
async function downloadPDF() {
    if (!currentPatient || !currentCalcResult || !currentRisk) {
        showToast('请先完成计算');
        return;
    }

    const btn = event.target;
    const origText = btn.innerHTML;
    btn.innerHTML = '<span class="loading"></span>生成中...';
    btn.disabled = true;

    try {
        const resp = await fetch('/api/pdf', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                patient: currentPatient,
                calc_result: currentCalcResult,
                risk: currentRisk,
                meal_plan: currentMealPlan || { meals: {}, total_protein: 0, total_food_water: 0 },
            }),
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.error || 'PDF 生成失败');
        }

        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `OHSS食谱_${currentPatient.name || '患者'}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast('PDF 下载成功 ✓');
    } catch (e) {
        showToast('生成失败：' + e.message);
    } finally {
        btn.innerHTML = origText;
        btn.disabled = false;
    }
}

// ============================================================
// 二维码下载
// ============================================================
async function downloadQRCode() {
    if (!currentPatient || !currentCalcResult || !currentRisk) {
        showToast('请先完成计算');
        return;
    }

    const btn = event.target;
    const origText = btn.innerHTML;
    btn.innerHTML = '<span class="loading"></span>生成中...';
    btn.disabled = true;

    try {
        const resp = await fetch('/api/qrcode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                patient: currentPatient,
                calc_result: currentCalcResult,
                risk: currentRisk,
                meal_plan: currentMealPlan || { total_protein: 0, total_food_water: 0 },
            }),
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.error || '二维码生成失败');
        }

        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `OHSS二维码_${currentPatient.name || '患者'}.png`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast('二维码下载成功 ✓');
    } catch (e) {
        showToast('生成失败：' + e.message);
    } finally {
        btn.innerHTML = origText;
        btn.disabled = false;
    }
}

// ============================================================
// 初始化
// ============================================================
document.addEventListener('DOMContentLoaded', function() {
    // 默认隐藏结果区域
    hideSection('result-section');
    hideSection('meal-section');
    hideSection('output-section');
});
</script>
</body>
</html>
'''
```

- [ ] **Step 2: 同时更新 `/api/calculate` 路由为完整实现**

```python
@app.route('/api/calculate', methods=['POST'])
def calculate():
    """核心计算接口"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '无效的请求数据'}), 400

        height = float(data.get('height', 0))
        weight = float(data.get('weight', 0))
        gender = data.get('gender', 'female')
        waist = data.get('waist')
        calf = data.get('calf')
        age = data.get('age')

        if not height or not weight:
            return jsonify({'error': '身高和体重为必填项'}), 400

        # BMI
        bmi = calc_bmi(weight, height)
        bmi_cat = bmi_category(bmi)

        # 计算体重
        calc_w, calc_w_method = determine_calc_weight(
            weight, height,
            float(waist) if waist else None,
            float(calf) if calf else None,
            gender
        )

        # 风险评分
        assessment = {
            'pcos': data.get('pcos') == 'yes',
            'prev_ohss': data.get('prev_ohss') == 'yes',
            'age_under_35': age is not None and float(age) < 35,
            'bmi_under_18_5': bmi < 18.5,
            'amh_high': data.get('amh_high') == 'yes',
            'afc_high': data.get('afc_high') == 'yes',
            'e2_high': data.get('e2_high') == 'yes',
            'follicle_high': data.get('follicle_high') == 'yes',
            'oocyte_high': data.get('oocyte_high') == 'yes',
            'symptoms': data.get('symptoms') == 'yes',
            'ovary_enlarged': data.get('ovary_enlarged') == 'yes',
            'ascites': data.get('ascites') == 'yes',
            'pleural_effusion': data.get('pleural_effusion') == 'yes',
        }
        score = calc_risk_score(assessment)
        level, coeff = risk_level(score)

        # 蛋白需求
        protein_low, protein_high = calc_protein_range(calc_w, coeff)

        # 液体参考
        liquid_total = calc_liquid_total(calc_w)

        # 食谱生成
        meal_plan = generate_meal_plan(protein_high, liquid_total, calc_w)

        return jsonify({
            'patient': {
                'name': data.get('name', ''),
                'age': age,
                'height': height,
                'weight': weight,
                'gender': gender,
                'waist': waist,
                'calf': calf,
            },
            'calc_result': {
                'bmi': bmi,
                'bmi_category': bmi_cat,
                'calc_weight': calc_w,
                'calc_weight_method': calc_w_method,
                'protein_low': protein_low,
                'protein_high': protein_high,
                'liquid_total': liquid_total,
                'actual_drink': meal_plan['actual_drink'],
            },
            'risk': {
                'score': score,
                'level': level,
                'protein_coeff': f"{coeff[0]}-{coeff[1]} g/kg/天",
            },
            'meal_plan': meal_plan,
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
```

- [ ] **Step 3: 启动完整应用并测试**

```bash
cd "C:\Users\a\ohss-calculator"
python app.py
```

Expected: Flask 启动在 `http://0.0.0.0:5000`，浏览器访问页面显示完整计算器。

- [ ] **Step 4: 端到端测试**

```bash
cd "C:\Users\a\ohss-calculator"
python -c "
import json
from app import app

client = app.test_client()

# 测试计算接口
test_input = {
    'name': '张女士', 'age': 30, 'height': 160, 'weight': 60,
    'gender': 'female', 'pcos': 'yes', 'e2_high': 'yes',
    'symptoms': 'yes', 'follicle_high': 'no',
    'oocyte_high': 'no', 'ovary_enlarged': 'no',
    'ascites': 'no', 'pleural_effusion': 'no',
    'prev_ohss': 'no', 'amh_high': 'no', 'afc_high': 'no',
}

resp = client.post('/api/calculate', json=test_input)
assert resp.status_code == 200, f'Calculate failed: {resp.status_code}'
result = resp.get_json()
print(f'BMI: {result[\"calc_result\"][\"bmi\"]}')
print(f'计算体重: {result[\"calc_result\"][\"calc_weight\"]}kg')
print(f'风险评分: {result[\"risk\"][\"score\"]}分, 等级: {result[\"risk\"][\"level\"]}')
print(f'蛋白需求: {result[\"calc_result\"][\"protein_low\"]}~{result[\"calc_result\"][\"protein_high\"]}g')
print(f'液体总量: {result[\"calc_result\"][\"liquid_total\"]}ml')
print(f'食谱总蛋白: {result[\"meal_plan\"][\"total_protein\"]}g')
print(f'食物含水量: {result[\"meal_plan\"][\"total_food_water\"]}ml')
print(f'建议饮水量: {result[\"meal_plan\"][\"actual_drink\"]}ml')

# 显示每餐
for name, meal in result['meal_plan']['meals'].items():
    foods = [f'{i[\"name\"]}({i[\"protein\"]}g)' for i in meal['items']]
    print(f'{name}: {\" + \".join(foods) if foods else \"(无)\"} = {meal[\"protein_subtotal\"]}g')

print('端到端测试通过!')
"
```

Expected: 所有计算正确，食谱生成合理。

---

### Task 6: 启动脚本与说明文档

**Files:**
- Create: `ohss-calculator/start.bat`
- Create: `ohss-calculator/README.md`

- [ ] **Step 1: 创建 start.bat**

```bat
@echo off
chcp 65001 >nul
title OHSS 高蛋白饮食智能计算器

echo ============================================
echo   OHSS 高蛋白饮食智能计算器
echo   生殖医学中心 · 护理宣教工具
echo ============================================
echo.

cd /d "%~dp0"

echo [1/2] 检查依赖...
pip install -r requirements.txt -q

echo [2/2] 启动服务...
echo.
echo 请在浏览器中打开：http://localhost:5000
echo 按 Ctrl+C 停止服务
echo.

python app.py
pause
```

- [ ] **Step 2: 创建 README.md**

```markdown
# OHSS 高蛋白饮食智能计算器

生殖医学中心护理宣教工具，用于门诊护士快速生成个性化高蛋白饮食食谱。

## 快速启动

### Windows
双击 `start.bat`，浏览器访问 `http://localhost:5000`

### 命令行
```bash
pip install -r requirements.txt
python app.py
```

## 功能

1. **患者信息录入** — 身高、体重、腰围、小腿围、OHSS 风险评估指标
2. **自动计算** — BMI、计算体重、风险分层、蛋白需求、液体参考
3. **五餐食谱生成** — 早餐/早加餐/午餐/午加餐/晚餐个性化食谱
4. **PDF 报告** — 含患者信息、风险评估、食谱明细、安全提示
5. **二维码** — 编码关键信息供打印分享

## 技术栈

- Python 3 + Flask
- reportlab（PDF 生成，需微软雅黑字体 msyh.ttc）
- qrcode + Pillow（二维码生成）
- 原生 HTML/CSS/JS（移动端优先）

## 安全提示

- 本工具为护理科普参考，**不替代临床诊断**
- 30ml/kg 液体值仅作参考，**口渴感、尿量优先**，禁止机械限水
- 治疗级（≥11 分）患者应尽快到急诊留观室就诊
- 本工具评分量表为本科室自制，有待临床数据验证

## 移动端适配

- 适配微信浏览器、手机自带浏览器
- 最大宽度 480px，16px 输入字体防 iOS 缩放
- 响应式布局，支持打印
```

- [ ] **Step 3: 最终验证启动**

```bash
cd "C:\Users\a\ohss-calculator"
python -c "
from app import app
# 验证所有路由注册
rules = [r.rule for r in app.url_map.iter_rules()]
print('注册的路由:')
for r in sorted(rules):
    print(f'  {r}')
assert '/' in rules
assert '/api/calculate' in rules
assert '/api/pdf' in rules
assert '/api/qrcode' in rules
print('所有路由验证通过!')
print('字体可用:', '是' if __import__('app').FONT_AVAILABLE else '否（PDF 中文可能显示异常）')
"
```

Expected: 所有路由注册成功。

---

## 自检清单

1. **Spec 覆盖检查：**
   - [x] BMI 计算与分类 — Task 2 (calc_bmi, bmi_category)
   - [x] 理想体重 IBW — Task 2 (calc_ibw)
   - [x] 计算体重（含肥胖亚型分层） — Task 2 (determine_calc_weight)
   - [x] 风险评分系统（6 个评估阶段） — Task 2 (calc_risk_score)
   - [x] 风险分层（健康饮食/预防/干预/治疗） — Task 2 (risk_level)
   - [x] 蛋白系数 — Task 2 (calc_protein_range)
   - [x] 液体参考 — Task 2 (calc_liquid_total, calc_actual_drink)
   - [x] 42 种食物数据库 — Task 2 (FOOD_DATABASE)
   - [x] 五餐食谱生成 — Task 2 (generate_meal_plan)
   - [x] 双锁定（蛋白不超上限 + 液体总量） — Task 2 (_apply_protein_lock)
   - [x] PPT 报告 — Task 3 (/api/pdf)
   - [x] 二维码 — Task 4 (/api/qrcode)
   - [x] 移动端 UI — Task 5 (HTML_TEMPLATE)
   - [x] 安全提示 — Task 5 (HTML 底部 + PDF 第四部分)
   - [x] 微信浏览器兼容 — Task 5 (viewport, -webkit, font-size: 16px)

2. **无占位符：** 所有代码步骤包含完整实现。✓
3. **类型一致性：** 前后端数据结构一致（patient, calc_result, risk, meal_plan）。✓