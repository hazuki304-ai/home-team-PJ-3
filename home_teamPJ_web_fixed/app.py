import os
import json
from datetime import datetime, date, timedelta, time
from functools import wraps
from collections import defaultdict

from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, abort
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func, text

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-change-this-secret")
db_url = os.getenv("DATABASE_URL", "sqlite:///home_team_pj.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif db_url.startswith("postgresql://") and "+psycopg" not in db_url:
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
app.config.update(
    SQLALCHEMY_DATABASE_URI=db_url,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
    REMEMBER_COOKIE_HTTPONLY=True,
    REMEMBER_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
)
db = SQLAlchemy(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "ログインしてください。"
login_manager.login_message_category = "warning"

ACTIVITIES = ["勉強", "運動", "睡眠", "その他"]
SUBJECTS = ["国語", "社会", "理科", "英語", "数学", "情報", "その他"]
EXERCISES = ["ウォーキング", "ランニング", "スイミング", "サイクリング", "その他"]
WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def get_id(self):
        return str(self.id)


class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    activity = db.Column(db.String(30), nullable=False)
    repeat_type = db.Column(db.String(20), nullable=False, default="1回のみ")
    weekday = db.Column(db.Integer, nullable=True)
    start = db.Column(db.DateTime, nullable=False)
    end = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey("schedule.id"), nullable=True)
    result_date = db.Column(db.Date, nullable=False, index=True)
    activity = db.Column(db.String(30), nullable=False)
    detail = db.Column(db.String(160), nullable=False, default="")
    duration_minutes = db.Column(db.Integer, nullable=False)
    start = db.Column(db.DateTime, nullable=False)
    end = db.Column(db.DateTime, nullable=False)
    source = db.Column(db.String(20), nullable=False, default="manual")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class LocationRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(300), nullable=False, default="")
    stay_time = db.Column(db.Integer, nullable=False, default=0)
    tag = db.Column(db.String(80), nullable=False, default="手動記録")


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


@app.context_processor
def inject_globals():
    return {"activities": ACTIVITIES, "weekdays": WEEKDAYS, "today": date.today(),
            "timedelta": timedelta}


def parse_date(value, default=None):
    if not value:
        return default or date.today()
    return date.fromisoformat(value)


def parse_clock(value):
    return datetime.strptime(value, "%H:%M").time()


def to_iso(dt):
    return dt.isoformat(timespec="seconds")


def own_or_404(model, item_id):
    item = db.session.get(model, item_id)
    if item is None or item.user_id != current_user.id:
        abort(404)
    return item


def week_monday(d):
    return d - timedelta(days=d.weekday())


def duration_minutes(start, end):
    if end <= start:
        end += timedelta(days=1)
    return int((end - start).total_seconds() // 60), end


def build_weekly_analysis(user_id, week_start):
    week_end = week_start + timedelta(days=6)
    rows = Result.query.filter(
        Result.user_id == user_id,
        Result.result_date >= week_start,
        Result.result_date <= week_end
    ).all()
    category_totals = defaultdict(int)
    daily_totals = defaultdict(int)
    for row in rows:
        category_totals[row.activity] += row.duration_minutes
        daily_totals[row.result_date.isoformat()] += row.duration_minutes
    categories = [
        {"category": k, "minutes": v, "hours": round(v / 60, 2),
         "share": round(v / max(sum(category_totals.values()), 1) * 100, 1)}
        for k, v in sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    ]
    daily = []
    for i in range(7):
        d = week_start + timedelta(days=i)
        mins = daily_totals[d.isoformat()]
        daily.append({"date": d.isoformat(), "weekday": WEEKDAYS[i],
                      "total_minutes": mins, "hours": round(mins / 60, 2)})
    previous_start = week_start - timedelta(days=7)
    previous_end = week_start - timedelta(days=1)
    previous_rows = Result.query.filter(
        Result.user_id == user_id,
        Result.result_date >= previous_start,
        Result.result_date <= previous_end
    ).all()
    previous = defaultdict(int)
    for row in previous_rows:
        previous[row.activity] += row.duration_minutes
    changes = {
        key: {"current_minutes": value, "previous_minutes": previous.get(key, 0),
              "change_minutes": value - previous.get(key, 0)}
        for key, value in category_totals.items()
    }
    observations = []
    if categories:
        observations.append(f"最も時間が多かった活動は「{categories[0]['category']}」で、{categories[0]['hours']:.1f}時間でした。")
    if daily:
        busiest = max(daily, key=lambda x: x["total_minutes"])
        observations.append(f"最も記録時間が長かった曜日は{busiest['weekday']}曜日（{busiest['hours']:.1f}時間）でした。")
    total = sum(category_totals.values())
    observations.append(f"今週の記録合計は{total / 60:.1f}時間です。")
    return {
        "available": bool(rows), "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(), "total_minutes": total,
        "categories": categories, "daily": daily,
        "category_changes": changes, "observations": observations,
        "previous_week": {"available": bool(previous_rows),
                          "category_totals": dict(previous)}
    }


def compare_weekly(user_id, week_start, activity=None):
    week_end = week_start + timedelta(days=6)
    totals = db.session.query(
        Result.user_id, func.sum(Result.duration_minutes)
    ).filter(Result.result_date >= week_start, Result.result_date <= week_end)
    if activity:
        totals = totals.filter(Result.activity == activity)
    totals = totals.group_by(Result.user_id).all()
    values = [{"user_id": uid, "minutes": int(total or 0)} for uid, total in totals]
    values.sort(key=lambda x: x["minutes"], reverse=True)
    mine = next((x for x in values if x["user_id"] == user_id), None)
    avg = sum(x["minutes"] for x in values) / len(values) if values else 0
    rank = next((i + 1 for i, x in enumerate(values) if x["user_id"] == user_id), None)
    return {
        "available": mine is not None, "mine_minutes": mine["minutes"] if mine else 0,
        "average_minutes": avg, "rank": rank, "total_users": len(values),
        "difference_minutes": (mine["minutes"] - avg) if mine else 0,
        "values": values
    }


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        uid = request.form.get("user_id", "").strip()
        password = request.form.get("password", "")
        display_name = request.form.get("display_name", "").strip() or uid
        if not uid or len(uid) > 50:
            flash("ユーザーIDを入力してください（50文字以内）。", "danger")
        elif len(password) < 8:
            flash("パスワードは8文字以上にしてください。", "danger")
        elif User.query.filter_by(user_id=uid).first():
            flash("このユーザーIDはすでに登録されています。", "danger")
        else:
            user = User(user_id=uid, display_name=display_name[:80],
                        password_hash=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("アカウントを作成しました。", "success")
            return redirect(url_for("dashboard"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        uid = request.form.get("user_id", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(user_id=uid).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            return redirect(url_for("dashboard"))
        flash("ユーザーIDまたはパスワードが正しくありません。", "danger")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    today = date.today()
    schedules = Schedule.query.filter_by(user_id=current_user.id).all()
    today_items = []
    for s in schedules:
        if ((s.repeat_type == "毎週" and s.weekday == today.weekday()) or
            (s.repeat_type == "1回のみ" and s.start.date() == today)):
            today_items.append(s)
    today_items.sort(key=lambda x: x.start.time())
    recent = Result.query.filter_by(user_id=current_user.id).order_by(Result.result_date.desc(), Result.start.desc()).limit(5).all()
    total = db.session.query(func.sum(Result.duration_minutes)).filter_by(
        user_id=current_user.id, result_date=today).scalar() or 0
    return render_template("dashboard.html", today_items=today_items, recent=recent, today_minutes=total)


@app.route("/schedules", methods=["GET", "POST"])
@login_required
def schedules():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        activity = request.form.get("activity", "勉強")
        repeat = request.form.get("repeat_type", "1回のみ")
        if not title or activity not in ACTIVITIES or repeat not in ("1回のみ", "毎週"):
            flash("入力内容を確認してください。", "danger")
            return redirect(url_for("schedules"))
        try:
            day = parse_date(request.form.get("schedule_date"))
            start_t, end_t = parse_clock(request.form.get("start")), parse_clock(request.form.get("end"))
            weekday = int(request.form.get("weekday", day.weekday())) if repeat == "毎週" else None
            if weekday is not None and weekday not in range(7):
                raise ValueError()
            anchor = day if repeat == "1回のみ" else date.today() + timedelta(days=(weekday - date.today().weekday()) % 7)
            start_dt = datetime.combine(anchor, start_t)
            end_dt = datetime.combine(anchor, end_t)
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)
            db.session.add(Schedule(user_id=current_user.id, title=title, activity=activity,
                                    repeat_type=repeat, weekday=weekday, start=start_dt, end=end_dt))
            db.session.commit()
            flash("予定を追加しました。", "success")
        except (ValueError, TypeError):
            flash("日付・時刻・曜日の入力を確認してください。", "danger")
        return redirect(url_for("schedules"))
    items = Schedule.query.filter_by(user_id=current_user.id).order_by(Schedule.start).all()
    return render_template("schedules.html", items=items)


@app.post("/schedules/<int:sid>/delete")
@login_required
def delete_schedule(sid):
    item = own_or_404(Schedule, sid)
    Result.query.filter_by(user_id=current_user.id, schedule_id=item.id).delete()
    db.session.delete(item)
    db.session.commit()
    flash("予定と関連する実績を削除しました。", "success")
    return redirect(url_for("schedules"))


@app.route("/records", methods=["GET", "POST"])
@login_required
def records():
    if request.method == "POST":
        try:
            activity = request.form.get("activity", "勉強")
            if activity not in ACTIVITIES:
                raise ValueError()
            day = parse_date(request.form.get("result_date"))
            start_dt = datetime.combine(day, parse_clock(request.form.get("start")))
            end_dt = datetime.combine(day, parse_clock(request.form.get("end")))
            mins, end_dt = duration_minutes(start_dt, end_dt)
            if mins <= 0 or mins > 24 * 60:
                raise ValueError()
            sid_raw = request.form.get("schedule_id", "")
            sid = int(sid_raw) if sid_raw else None
            if sid:
                own_or_404(Schedule, sid)
            detail = request.form.get("detail", "").strip()[:160]
            db.session.add(Result(user_id=current_user.id, schedule_id=sid, result_date=day,
                                  activity=activity, detail=detail, duration_minutes=mins,
                                  start=start_dt, end=end_dt, source="manual"))
            db.session.commit()
            flash("実績を保存しました。", "success")
        except (ValueError, TypeError):
            flash("入力内容を確認してください。", "danger")
        return redirect(url_for("records"))
    items = Result.query.filter_by(user_id=current_user.id).order_by(Result.result_date.desc(), Result.start.desc()).limit(100).all()
    my_schedules = Schedule.query.filter_by(user_id=current_user.id).order_by(Schedule.title).all()
    return render_template("records.html", items=items, my_schedules=my_schedules)


@app.post("/records/<int:rid>/delete")
@login_required
def delete_record(rid):
    item = own_or_404(Result, rid)
    db.session.delete(item)
    db.session.commit()
    flash("実績を削除しました。", "success")
    return redirect(url_for("records"))


@app.route("/analysis")
@login_required
def analysis():
    try:
        selected = parse_date(request.args.get("week"), week_monday(date.today()))
    except (TypeError, ValueError):
        selected = week_monday(date.today())
        flash("週の指定が正しくなかったため、今週を表示します。", "warning")
    selected = week_monday(selected)
    data = build_weekly_analysis(current_user.id, selected)
    comparison = compare_weekly(current_user.id, selected)
    public_users = {u.id: u.display_name for u in User.query.all()}
    for item in comparison["values"]:
        item["display_name"] = "あなた" if item["user_id"] == current_user.id else public_users.get(item["user_id"], "ユーザー")
    return render_template("analysis.html", data=data, comparison=comparison,
                           week=selected, previous=selected-timedelta(days=7),
                           next_week=selected+timedelta(days=7), names=public_users)


@app.post("/analysis/ai")
@login_required
def analysis_ai():
    selected = week_monday(parse_date(request.form.get("week")))
    data = build_weekly_analysis(current_user.id, selected)
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return jsonify({"ok": True, "text": "\n".join(data["observations"]) + "\n\nOPENAI_API_KEYが未設定のため、基本集計による振り返りを表示しています。"})
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        payload = {
            "week": data["week_start"], "categories": data["categories"],
            "daily": data["daily"], "observations": data["observations"],
            "previous_week": data["previous_week"]
        }
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            instructions="あなたは学習・生活記録の振り返りを支援します。記録にない事実を推測せず、日本語で具体的かつ前向きに分析してください。健康状態を診断せず、過度な勉強や睡眠制限を勧めないでください。",
            input=json.dumps(payload, ensure_ascii=False)
        )
        return jsonify({"ok": True, "text": response.output_text})
    except Exception:
        app.logger.exception("AI reflection failed")
        return jsonify({"ok": False, "text": "AI分析を利用できませんでした。通常の集計は引き続き利用できます。" }), 503


@app.route("/locations")
@login_required
def locations():
    items = LocationRecord.query.filter_by(user_id=current_user.id).order_by(LocationRecord.timestamp.desc()).limit(200).all()
    return render_template("locations.html", items=items)


@app.post("/api/locations")
@login_required
def save_location():
    payload = request.get_json(silent=True) or {}
    try:
        lat, lon = float(payload["latitude"]), float(payload["longitude"])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError()
        tag = str(payload.get("tag", "位置記録"))[:80]
        address = str(payload.get("address", ""))[:300]
        timestamp = datetime.utcnow()
        record = LocationRecord(user_id=current_user.id, timestamp=timestamp,
                                latitude=lat, longitude=lon, address=address,
                                stay_time=max(0, min(int(payload.get("stay_time", 0)), 604800)),
                                tag=tag)
        db.session.add(record)
        db.session.commit()
        return jsonify({"ok": True, "id": record.id, "timestamp": to_iso(timestamp)})
    except (KeyError, ValueError, TypeError):
        return jsonify({"ok": False, "error": "座標または記録内容が不正です。"}), 400


@app.post("/locations/<int:rid>/delete")
@login_required
def delete_location(rid):
    item = own_or_404(LocationRecord, rid)
    db.session.delete(item)
    db.session.commit()
    flash("位置情報記録を削除しました。", "success")
    return redirect(url_for("locations"))


@app.post("/api/locations/clear")
@login_required
def clear_locations():
    LocationRecord.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({"ok": True})


@app.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ok"})
    except Exception:
        return jsonify({"status": "database_error"}), 503


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=True)
