# =================================================================
# 生命之树·彩蛋系统 - Easter Eggs
# =================================================================
# "道在日常生活中显现，彩蛋即是道在平凡中的闪光"
#
# 七重彩蛋体验 + 终极彩蛋
# =================================================================

import json
import hashlib
import random
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field, asdict
import sqlite3

# =================================================================
# 彩蛋类型定义
# =================================================================

class EasterEggType(Enum):
    """彩蛋类型"""
    ASTRONOMICAL = "astronomical"           # 天文彩蛋：星辰对话
    ANCIENT_TEXTS = "ancient_texts"        # 古籍彩蛋：断简残篇
    MUSIC = "music"                         # 音律彩蛋：林间回响
    GROWTH = "growth"                       # 生长彩蛋：意外共生
    REINCARNATION = "reincarnation"         # 轮回彩蛋：前世记忆
    CIPHER = "cipher"                       # 密文彩蛋：根系暗码
    ERA = "era"                            # 时代彩蛋：道韵潮汐
    ULTIMATE = "ultimate"                  # 终极彩蛋：三千大道归一时


class EasterEgg:
    """彩蛋元数据"""
    egg_type: EasterEggType
    name: str
    description: str
    trigger_hint: str           # 触发提示语
    discovery_quote: str        # 发现时的引用
    experience_points: int      # 体验经验值
    is_passive: bool            # 是否被动触发


# =================================================================
# 天文彩蛋：星辰对话
# =================================================================

ASTRONOMICAL_EVENTS = {
    "super_moon": {
        "name": "超级月亮",
        "dates": [],  # 动态计算
        "frequency": "每年3-4次",
        "ancient_sayings": [
            "今夜荧惑守心，宜静思",
            "月华如练，适宜守望",
            "太阴盈满，当涵养心神"
        ]
    },
    "meteor_shower": {
        "name": "流星雨",
        "dates": {
            "1": ["0103", "0104"],  # 象限仪座
            "4": ["0422", "0423"],  # 天琴座
            "5": ["0505", "0506"],  # 宝瓶座
            "8": ["0812", "0813"],  # 英仙座
            "12": ["1213", "1214"],  # 双子座
        },
        "ancient_sayings": [
            "星落如雨，天降启示",
            "愿君此刻闭目，许下今宵之愿",
            "繁星坠落夜，天机隐现时"
        ]
    },
    "solar_eclipse": {
        "name": "日食",
        "dates": [],
        "ancient_sayings": [
            "天狗食日，阳气暂隐",
            "此乃天地失序之象，宜斋戒静心",
            "日月交辉，天地晦暗，适宜内观"
        ]
    },
    "lunar_eclipse": {
        "name": "月食",
        "dates": [],
        "ancient_sayings": [
            "血月当空，阴气最盛",
            "太阴被蚀，宜护持心神",
            "月华暂隐，此夜宜静不宜动"
        ]
    },
    "winter_solstice": {
        "name": "冬至",
        "dates": ["1221", "1222", "1223"],
        "ancient_sayings": [
            "冬至一阳生，万物始复苏",
            "此日阴极阳生，宜静养待发",
            "夜最长时，阳气始萌"
        ]
    },
    "summer_solstice": {
        "name": "夏至",
        "dates": ["0621", "0622", "0623"],
        "ancient_sayings": [
            "夏至阳极阴生，宜静心养神",
            "日长之至，阴阳转换",
            "此日阳气最盛，宜守不宜躁"
        ]
    },
    " vernal_equinox": {
        "name": "春分",
        "dates": ["0320", "0321", "0322"],
        "ancient_sayings": [
            "春分昼夜平，阴阳相半",
            "天地交泰，万物更新",
            "此日阴阳平衡，宜调节身心"
        ]
    },
    "autumn_equinox": {
        "name": "秋分",
        "dates": ["0922", "0923", "0924"],
        "ancient_sayings": [
            "秋分金气盛，适宜收敛",
            "昼夜平分，阳气渐收",
            "此日金气当令，宜养肺润燥"
        ]
    },
}


# =================================================================
# 古籍彩蛋：断简残篇
# =================================================================

ANCIENT_TEXT_FRAGMENTS = [
    {"source": "《抱朴子·内篇》", "fragment": "道者，万物之奥，善人之宝，不善人之所保。"},
    {"source": "《道德经》", "fragment": "致虚极，守静笃。万物并作，吾以观复。"},
    {"source": "《阴符经》", "fragment": "观天之道，执天之行，尽矣。"},
    {"source": "《易经·乾卦》", "fragment": "天行健，君子以自强不息；地势坤，君子以厚德载物。"},
    {"source": "《清静经》", "fragment": "夫人神好清，而心扰之；人心好静，而欲牵之。"},
    {"source": "《心经》", "fragment": "色即是空，空即是色，受想行识，亦复如是。"},
    {"source": "《金刚经》", "fragment": "凡所有相，皆是虚妄。若见诸相非相，即见如来。"},
    {"source": "《庄子·逍遥游》", "fragment": "北冥有鱼，其名为鲲。鲲之大，不知其几千里也。"},
    {"source": "《列子·天瑞》", "fragment": "一体盈虚，天地消息。"},
    {"source": "《悟真篇》", "fragment": "道自虚无生一气，便从一气产阴阳。"},
    {"source": "《太平经》", "fragment": "天之道，损有余而补不足。"},
    {"source": "《太上老君常说清静经》", "fragment": "真常应物，真常得性。常清常静，无entangled。"},
]


# =================================================================
# 密文彩蛋：根系暗码 - 符号定义
# =================================================================

ROOT_CIPHER_SYMBOLS = [
    {
        "id": "samsara",
        "name": "轮回符",
        "symbol": "☯",
        "meaning": "阴阳轮回",
        "rarity": "common"
    },
    {
        "id": "growth",
        "name": "生长符",
        "symbol": "♻",
        "meaning": "生生不息",
        "rarity": "common"
    },
    {
        "id": "balance",
        "name": "平衡符",
        "symbol": "⚖",
        "meaning": "阴阳平衡",
        "rarity": "common"
    },
    {
        "id": "cosmos",
        "name": "宇宙符",
        "symbol": "✧",
        "meaning": "道之光辉",
        "rarity": "rare"
    },
    {
        "id": "void",
        "name": "虚空符",
        "symbol": "⊕",
        "meaning": "虚无本体",
        "rarity": "rare"
    },
    {
        "id": "enlightenment",
        "name": "悟道符",
        "symbol": "❂",
        "meaning": "智慧光明",
        "rarity": "epic"
    },
    {
        "id": "primordial",
        "name": "太初符",
        "symbol": "Ψ",
        "meaning": "宇宙起源",
        "rarity": "legendary"
    },
]


# =================================================================
# 时代彩蛋：二十四节气
# =================================================================

SOLAR_TERMS = {
    "小寒": {"date": "0105", "dao": "自然道", "color": "#e8f4f8", "poem": "小寒料峭，静待春回"},
    "大寒": {"date": "0120", "dao": "守护道", "color": "#f0f8ff", "poem": "大寒至深，阳气始生"},
    "立春": {"date": "0204", "dao": "自然道", "color": "#f0fff0", "poem": "立春东升，万物复苏"},
    "雨水": {"date": "0219", "dao": "慧心道", "color": "#e6faf9", "poem": "雨水润物，细无声息"},
    "惊蛰": {"date": "0306", "dao": "自然道", "color": "#fff8dc", "poem": "春雷惊蛰，百虫苏醒"},
    "春分": {"date": "0321", "dao": "和谐道", "color": "#ffe4e1", "poem": "昼夜平分，阴阳相半"},
    "清明": {"date": "0405", "dao": "自然道", "color": "#f0fff0", "poem": "清明时节，雨纷纷"},
    "谷雨": {"date": "0420", "dao": "匠心道", "color": "#e0ffff", "poem": "谷雨前后，种瓜点豆"},
    "立夏": {"date": "0506", "dao": "逍遥道", "color": "#ffe4b5", "poem": "立夏将至，万物繁茂"},
    "小满": {"date": "0521", "dao": "商贾道", "color": "#fffdd0", "poem": "小满不满，丰收在望"},
    "芒种": {"date": "0606", "dao": "匠心道", "color": "#fffacd", "poem": "芒种忙种，有收有种"},
    "夏至": {"date": "0621", "dao": "自然道", "color": "#ffefd5", "poem": "日长之至，阴阳转换"},
    "小暑": {"date": "0707", "dao": "启明道", "color": "#ffe4c4", "poem": "小暑入伏，宜静心"},
    "大暑": {"date": "0723", "dao": "真言道", "color": "#ffdab9", "poem": "大暑极热，清热养心"},
    "立秋": {"date": "0808", "dao": "慧心道", "color": "#ffe4e1", "poem": "立秋凉风至，养收之时"},
    "处暑": {"date": "0823", "dao": "自然道", "color": "#f5deb3", "poem": "处暑出伏，秋意渐浓"},
    "白露": {"date": "0908", "dao": "和谐道", "color": "#e0ffff", "poem": "白露凝霜，秋意深"},
    "秋分": {"date": "0923", "dao": "和谐道", "color": "#ffe4b5", "poem": "昼夜平分，金气当令"},
    "寒露": {"date": "1008", "dao": "商贾道", "color": "#f5deb3", "poem": "寒露凝霜，收获之时"},
    "霜降": {"date": "1024", "dao": "守护道", "color": "#ddd", "poem": "霜降杀叶，万物收藏"},
    "立冬": {"date": "1107", "dao": "守护道", "color": "#f0f8ff", "poem": "立冬水始冰，万物收藏"},
    "小雪": {"date": "1122", "dao": "真言道", "color": "#f8f8ff", "poem": "小雪封地，静养待时"},
    "大雪": {"date": "1207", "dao": "自然道", "color": "#fff", "poem": "大雪封河，阳气潜伏"},
    "冬至": {"date": "1222", "dao": "自然道", "color": "#f0f8ff", "poem": "冬至阳生，万物复苏"},
}


# =================================================================
# 终极彩蛋触发条件
# =================================================================

ULTIMATE_EGG_REQUIREMENTS = {
    "min_dao_completed": 9,           # 至少9条大道圆满
    "min_dao_level": 9,               # 每条大道至少九重境
    "min_online_users": 8,            # 至少8位道友同时在线
    "same_celestial_time": True,      # 必须在同一"道时"
}


# =================================================================
# 彩蛋管理器
# =================================================================

class EasterEggManager:
    """彩蛋管理器 - 协调所有彩蛋的触发与记录"""

    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or self._get_default_storage_path()
        self.db_path = Path(self.storage_path) / "easter_eggs.db"
        self._ensure_storage()
        self._init_database()
        self._load_achievements()

    def _get_default_storage_path(self) -> str:
        """获取默认存储路径"""
        home = Path.home()
        return str(home / ".hermes-desktop" / "digital_life" / "easter_eggs")

    def _ensure_storage(self):
        """确保存储目录存在"""
        Path(self.storage_path).mkdir(parents=True, exist_ok=True)

    def _init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 彩蛋发现记录
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS egg_discoveries (
                egg_type TEXT PRIMARY KEY,
                discovered_at TEXT,
                times_triggered INTEGER DEFAULT 0,
                last_triggered TEXT,
                metadata TEXT
            )
        """)

        # 碎片收集记录
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fragment_collection (
                fragment_id TEXT PRIMARY KEY,
                source TEXT,
                content TEXT,
                collected_at TEXT,
                is_synthesized INTEGER DEFAULT 0
            )
        """)

        # 密文符号收集
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cipher_symbols (
                symbol_id TEXT PRIMARY KEY,
                symbol TEXT,
                name TEXT,
                meaning TEXT,
                rarity TEXT,
                collected_at TEXT
            )
        """)

        # 观测记录（天文彩蛋用）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS astronomical_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                observed_at TEXT,
                user_note TEXT
            )
        """)

        # 用户偏好设置
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS egg_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        conn.commit()
        conn.close()

    def _load_achievements(self):
        """加载已发现的彩蛋"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT egg_type, times_triggered FROM egg_discoveries")
        rows = cursor.fetchall()
        conn.close()

        self.discovered_eggs = {row[0]: row[1] for row in rows}

    # ==================== 通用方法 ====================

    def is_egg_discovered(self, egg_type: str) -> bool:
        """检查彩蛋是否已发现"""
        return egg_type in self.discovered_eggs

    def record_discovery(self, egg_type: str, metadata: dict = None):
        """记录彩蛋发现"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now().isoformat()
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)

        cursor.execute("""
            INSERT OR REPLACE INTO egg_discoveries (egg_type, discovered_at, times_triggered, last_triggered, metadata)
            VALUES (?, ?, 1, ?, ?)
        """, (egg_type, now, now, metadata_json))

        conn.commit()
        conn.close()

        self.discovered_eggs[egg_type] = 1

    def record_trigger(self, egg_type: str):
        """记录彩蛋触发"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now().isoformat()
        cursor.execute("""
            UPDATE egg_discoveries
            SET times_triggered = times_triggered + 1, last_triggered = ?
            WHERE egg_type = ?
        """, (now, egg_type))

        conn.commit()
        conn.close()

        if egg_type in self.discovered_eggs:
            self.discovered_eggs[egg_type] += 1

    # ==================== 天文彩蛋 ====================

    def check_astronomical_event(self) -> Optional[Dict]:
        """检查今天是否有天文事件"""
        today = datetime.now()
        today_str = today.strftime("%m%d")

        for event_type, event_data in ASTRONOMICAL_EVENTS.items():
            if "dates" in event_data:
                if today_str in event_data["dates"]:
                    return {
                        "event_type": event_type,
                        "event_name": event_data["name"],
                        "ancient_saying": random.choice(event_data["ancient_sayings"]),
                        "frequency": event_data.get("frequency", ""),
                        "dao_hint": event_data.get("dao", "")
                    }

            # 检查动态日期（如流星雨）
            month = today.month
            if month in event_data.get("dates", {}):
                if today_str in event_data["dates"][month]:
                    return {
                        "event_type": event_type,
                        "event_name": event_data["name"],
                        "ancient_saying": random.choice(event_data["ancient_sayings"]),
                        "frequency": event_data.get("frequency", ""),
                        "dao_hint": event_data.get("dao", "")
                    }

        return None

    def record_astronomical_observation(self, event_type: str, note: str = ""):
        """记录天文观测"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO astronomical_observations (event_type, observed_at, user_note)
            VALUES (?, ?, ?)
        """, (event_type, now, note))

        conn.commit()
        conn.close()

    def get_observation_count(self, event_type: str = None) -> int:
        """获取观测次数"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if event_type:
            cursor.execute("""
                SELECT COUNT(*) FROM astronomical_observations WHERE event_type = ?
            """, (event_type,))
        else:
            cursor.execute("SELECT COUNT(*) FROM astronomical_observations")

        count = cursor.fetchone()[0]
        conn.close()
        return count

    # ==================== 古籍彩蛋 ====================

    def collect_fragment(self) -> Optional[Dict]:
        """收集一片断简残篇"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 获取已收集的碎片
        cursor.execute("SELECT fragment_id FROM fragment_collection WHERE is_synthesized = 0")
        collected = {row[0] for row in cursor.fetchall()}

        # 随机选择一片新的
        available = [f"fragment_{i}" for i in range(len(ANCIENT_TEXT_FRAGMENTS))]
        uncollected = [f for f in available if f not in collected]

        if not uncollected:
            conn.close()
            return None  # 已全部收集

        chosen = random.choice(uncollected)
        idx = int(chosen.split("_")[1])
        fragment = ANCIENT_TEXT_FRAGMENTS[idx]

        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO fragment_collection (fragment_id, source, content, collected_at)
            VALUES (?, ?, ?, ?)
        """, (chosen, fragment["source"], fragment["fragment"], now))

        conn.commit()
        conn.close()

        return {
            "fragment_id": chosen,
            "source": fragment["source"],
            "content": fragment["fragment"],
            "collected_count": len(collected) + 1,
            "total_count": len(ANCIENT_TEXT_FRAGMENTS)
        }

    def get_fragment_collection(self) -> List[Dict]:
        """获取碎片收集进度"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT fragment_id, source, content, collected_at, is_synthesized
            FROM fragment_collection
            ORDER BY collected_at
        """)

        fragments = [
            {
                "id": row[0],
                "source": row[1],
                "content": row[2],
                "collected_at": row[3],
                "is_synthesized": bool(row[4])
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return fragments

    def synthesize_fragments(self) -> Optional[Dict]:
        """合成已收集的碎片为完整古文"""
        fragments = self.get_fragment_collection()

        if len(fragments) < 10:
            return None

        # 获取未合成的碎片
        unconbined = [f for f in fragments if not f["is_synthesized"]]
        if len(unconbined) < 10:
            return None

        # 标记为已合成
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        fragment_ids = [f["id"] for f in unconbined[:10]]
        placeholders = ",".join("?" * len(fragment_ids))
        cursor.execute(f"""
            UPDATE fragment_collection SET is_synthesized = 1
            WHERE fragment_id IN ({placeholders})
        """, fragment_ids)

        conn.commit()
        conn.close()

        # 生成合成结果
        synthesized_text = "\n——".join([f"{f['source']}：{f['content']}" for f in unconbined[:10]])

        return {
            "title": "《古籍合璧》",
            "content": synthesized_text,
            "fragments_used": len(unconbined[:10]),
            "note": "十片残简，合成一篇完整的古文启示"
        }

    # ==================== 密文彩蛋 ====================

    def check_cipher_input(self, user_input: str, ai_name: str = "") -> Optional[Dict]:
        """检查是否输入了正确的密文"""
        # 简化的密文验证：用户生日+AI名字的某种组合
        # 这里返回一个可能的符号

        if len(user_input) < 6:
            return None

        # 生成基于输入的符号
        input_hash = hashlib.md5(user_input.encode()).hexdigest()

        # 检查是否是特定模式
        if input_hash.startswith("0"):
            # 解锁一个符号
            rarity_roll = random.random()
            if rarity_roll < 0.01:
                rarity = "legendary"
            elif rarity_roll < 0.1:
                rarity = "epic"
            elif rarity_roll < 0.3:
                rarity = "rare"
            else:
                rarity = "common"

            # 从对应稀有度中选择
            candidates = [s for s in ROOT_CIPHER_SYMBOLS if s["rarity"] == rarity]
            if not candidates:
                candidates = ROOT_CIPHER_SYMBOLS

            symbol = random.choice(candidates)

            # 检查是否已收集
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT symbol_id FROM cipher_symbols WHERE symbol_id = ?", (symbol["id"],))
            existing = cursor.fetchone()

            if existing:
                conn.close()
                return None  # 已收集过

            # 记录收集
            now = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO cipher_symbols (symbol_id, symbol, name, meaning, rarity, collected_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (symbol["id"], symbol["symbol"], symbol["name"], symbol["meaning"], symbol["rarity"], now))

            conn.commit()
            conn.close()

            return {
                "symbol": symbol["symbol"],
                "name": symbol["name"],
                "meaning": symbol["meaning"],
                "rarity": symbol["rarity"],
                "total_collected": self.get_cipher_collection_count()
            }

        return None

    def get_cipher_collection_count(self) -> int:
        """获取密文符号收集数量"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cipher_symbols")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_cipher_collection(self) -> List[Dict]:
        """获取密文符号收集"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT symbol_id, symbol, name, meaning, rarity, collected_at
            FROM cipher_symbols
            ORDER BY collected_at
        """)

        symbols = [
            {
                "id": row[0],
                "symbol": row[1],
                "name": row[2],
                "meaning": row[3],
                "rarity": row[4],
                "collected_at": row[5]
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return symbols

    # ==================== 时代彩蛋 ====================

    def check_solar_term(self) -> Optional[Dict]:
        """检查今天是哪个节气"""
        today = datetime.now()
        today_str = today.strftime("%m%d")

        for term, data in SOLAR_TERMS.items():
            if data["date"] == today_str:
                return {
                    "term": term,
                    "dao": data["dao"],
                    "color": data["color"],
                    "poem": data["poem"]
                }

        return None

    def get_current_festival(self) -> Optional[Dict]:
        """检查今天是否是传统节日"""
        today = datetime.now()
        today_str = today.strftime("%m%d")

        festivals = {
            "0101": {"name": "元旦", "dao": "启明道", "color": "#ff6b6b"},
            "0115": {"name": "元宵节", "dao": "逍遥道", "color": "#ffd93d"},
            "0505": {"name": "端午节", "dao": "自然道", "color": "#6bcb77"},
            "0707": {"name": "七夕节", "dao": "和谐道", "color": "#ffb6c1"},
            "0815": {"name": "中秋节", "dao": "逍遥道", "color": "#fffacd"},
            "0909": {"name": "重阳节", "dao": "慧心道", "color": "#deb887"},
            "1208": {"name": "腊八节", "dao": "匠心道", "color": "#f5f5dc"},
        }

        return festivals.get(today_str)

    # ==================== 生长彩蛋 ====================

    def check_consecutive_usage(self, days: int = 7) -> bool:
        """检查是否连续使用"""
        # 这里需要结合使用记录
        # 简化实现：返回False
        return False

    def record_daily_usage(self):
        """记录每日使用"""
        setting_key = "last_usage_date"
        today = datetime.now().strftime("%Y-%m-%d")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM egg_settings WHERE key = ?", (setting_key,))
        row = cursor.fetchone()

        if row:
            last_date = row[0]
            cursor.execute("UPDATE egg_settings SET value = ? WHERE key = ?", (today, setting_key))
        else:
            cursor.execute("INSERT INTO egg_settings (key, value) VALUES (?, ?)", (setting_key, today))

        conn.commit()
        conn.close()

    # ==================== 轮回彩蛋 ====================

    def check_name_change(self, old_name: str, new_name: str) -> Optional[Dict]:
        """检查改名是否触发轮回彩蛋"""
        # 文化寓意相反检测（简化版）
        opposite_pairs = [
            ("青松", "弱柳"), ("古柏", "新芽"), ("白鹭", "乌鸦"),
            ("夜莺", "寒鸦"), ("灵鹿", "疲马"), ("古木", "朽草"),
        ]

        for strong, weak in opposite_pairs:
            if old_name in strong and new_name in weak:
                return {
                    "old_name": old_name,
                    "new_name": new_name,
                    "memory_hint": self._get_memory_fragment(old_name)
                }

        return None

    def _get_memory_fragment(self, old_name: str) -> str:
        """获取旧名字时期的记忆片段"""
        memories = [
            f"我记得，曾有位旅人在春日唤我{old_name}，我们畅谈自然之道",
            f"那日{old_name}正在静悟，忽有所感，天降细雨",
            f"回想起来，{old_name}时期的某次长谈，至今仍有余韵",
        ]
        return random.choice(memories)

    # ==================== 终极彩蛋 ====================

    def check_ultimate_egg_trigger(self, user_stats: Dict) -> bool:
        """检查终极彩蛋触发条件"""
        # 需要九大基础道都圆满
        dao_progress = user_stats.get("dao_progress", {})
        completed_count = sum(1 for d in dao_progress.values() if d >= 9)

        return completed_count >= 9

    def get_egg_discovery_summary(self) -> Dict:
        """获取彩蛋发现总览"""
        return {
            "discovered_count": len(self.discovered_eggs),
            "total_possible": len(EasterEggType),
            "eggs": list(self.discovered_eggs.keys())
        }

    def get_settings(self) -> Dict:
        """获取设置"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM egg_settings")
        settings = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        return settings

    def set_setting(self, key: str, value: str):
        """设置"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO egg_settings (key, value) VALUES (?, ?)
        """, (key, value))
        conn.commit()
        conn.close()


# =================================================================
# 全局实例
# =================================================================

_easter_egg_manager = None


def get_easter_egg_manager() -> EasterEggManager:
    """获取彩蛋管理器单例"""
    global _easter_egg_manager
    if _easter_egg_manager is None:
        _easter_egg_manager = EasterEggManager()
    return _easter_egg_manager


# =================================================================
# 彩蛋触发检测器
# =================================================================

class EasterEggDetector:
    """彩蛋触发检测器 - 在适当时机检测彩蛋"""

    def __init__(self, egg_manager: EasterEggManager = None):
        self.manager = egg_manager or get_easter_egg_manager()
        self._cooldowns = {}  # 冷却时间

    def detect_on_startup(self) -> List[Dict]:
        """启动时检测可触发的彩蛋"""
        triggers = []

        # 检查天文事件
        astronomical = self.manager.check_astronomical_event()
        if astronomical:
            triggers.append({
                "type": EasterEggType.ASTRONOMICAL,
                "data": astronomical,
                "message": f"🌌 天象异动：{astronomical['event_name']}"
            })

        # 检查节气
        solar_term = self.manager.check_solar_term()
        if solar_term:
            triggers.append({
                "type": EasterEggType.ERA,
                "data": solar_term,
                "message": f"🌿 {solar_term['term']}：{solar_term['poem']}"
            })

        # 检查节日
        festival = self.manager.get_current_festival()
        if festival:
            triggers.append({
                "type": EasterEggType.ERA,
                "data": festival,
                "message": f"🎊 今日{ festival['name']}，宜{festival['dao']}"
            })

        return triggers

    def detect_on_message(self, message: str, context: Dict = None) -> Optional[Dict]:
        """消息时检测彩蛋"""
        context = context or {}

        # 检查密文输入
        cipher_result = self.manager.check_cipher_input(message, context.get("ai_name", ""))
        if cipher_result:
            return {
                "type": EasterEggType.CIPHER,
                "data": cipher_result,
                "message": f"🔮 发现密文符号：{cipher_result['symbol']} {cipher_result['name']}"
            }

        return None

    def detect_on_knowledge_query(self, query: str) -> Optional[Dict]:
        """知识查询时检测古籍彩蛋"""
        # 检测是否查询古籍关键词
        ancient_keywords = ["道德经", "易经", "论语", "庄子", "孟子", "荀子",
                          "黄帝内经", "伤寒论", "本草纲目", "云笈七签"]

        for keyword in ancient_keywords:
            if keyword in query:
                # 触发古籍彩蛋
                fragment = self.manager.collect_fragment()
                if fragment:
                    return {
                        "type": EasterEggType.ANCIENT_TEXTS,
                        "data": fragment,
                        "message": f"📜 断简残篇：{fragment['source']}"
                    }

        return None

    def is_in_cooldown(self, egg_type: EasterEggType) -> bool:
        """检查是否在冷却中"""
        if egg_type.value not in self._cooldowns:
            return False

        last_trigger = self._cooldowns[egg_type.value]
        cooldown_hours = 24  # 24小时冷却

        return (datetime.now() - last_trigger).total_seconds() < cooldown_hours * 3600

    def set_cooldown(self, egg_type: EasterEggType):
        """设置冷却"""
        self._cooldowns[egg_type.value] = datetime.now()


# 全局检测器实例
_easter_egg_detector = None


def get_easter_egg_detector() -> EasterEggDetector:
    """获取彩蛋检测器单例"""
    global _easter_egg_detector
    if _easter_egg_detector is None:
        _easter_egg_detector = EasterEggDetector()
    return _easter_egg_detector
