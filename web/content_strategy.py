"""Shared content strategy and platform metadata rules.

This module is the single place for strategy labels, captions, platform tags,
CTA policy, and default Upload-Post metadata. Keep it dependency-light so both
FastAPI routes and standalone scripts can import it.
"""
from __future__ import annotations

import hashlib
import re
from typing import Callable


STRATEGY_LABEL = {
    "tech_judgement": "DORO 科技判讀",
    "tech": "科技",
    "tech_tutorial": "科技教學",
    "quote_analysis": "名人語錄解析",
    "figure_tech": "科技大咖解析",
    "figure_entertainment": "娛樂咖解析",
    "entertainment": "娛樂",
    "business_finance": "商業判讀",
    "finance": "財經",
    "pet": "寵物",
    "generic": "新聞",
}

STRATEGY_CTA_GROUP = {
    "tech_judgement": "tech",
    "tech": "tech",
    "tech_tutorial": "tech",
    "quote_analysis": "tech",
    "figure_tech": "tech",
    "finance": "none",
    "business_finance": "none",
    "figure_entertainment": "entertain",
    "entertainment": "entertain",
    "pet": "pet",
    "generic": "entertain",
}

MANYCHAT_CTA_STRATEGIES = {
    "tech_judgement",
    "tech",
    "tech_tutorial",
    "quote_analysis",
    "figure_tech",
}

IS_AIGC_BY_STRATEGY = {
    "tech_judgement": True,
    "tech": True,
    "tech_tutorial": True,
    "quote_analysis": True,
    "figure_tech": True,
    "figure_entertainment": False,
    "generic": True,
    "business_finance": True,
    "finance": True,
    "entertainment": False,
    "pet": False,
}

TITLE_FORMULA = {
    "tech_judgement": "{hook}｜DORO 科技判讀",
    "tech": "{hook}｜{n} 則 AI 大事一次看完",
    "tech_tutorial": "{hook}｜{n} 招 AI 技巧學起來",
    "quote_analysis": "{hook}｜一句話拆解 AI 時代的工作方式",
    "figure_tech": "{hook}｜科技大咖原片解析",
    "figure_entertainment": "{hook}｜娛樂咖原片解析",
    "entertainment": "{hook}｜今天台灣 {n} 件熱搜一次看",
    "business_finance": "{hook}｜商業判讀",
    "finance": "{hook}｜{n} 則市場焦點",
    "pet": "{hook}｜{n} 個萌寵時刻",
    "generic": "{hook}｜{n} 則今日重點",
}

SIGNOFF = {
    "tech_judgement": "追蹤 @_doro1998ai，每天看懂一件科技大事。",
    "tech": "追蹤 @_doro1998ai 每天一則 AI 懶人包 🐾",
    "tech_tutorial": "想學更多 AI 技巧？追蹤 @_doro1998ai 每天教你一招 🐾",
    "quote_analysis": "想看更多 AI 思維拆解？追蹤 @_doro1998ai 每天一個觀點 🐾",
    "figure_tech": "想看更多科技大咖原片解析？追蹤 @_doro1998ai 每天拆一段 🐾",
    "figure_entertainment": "想看更多娛樂咖原片解析？追蹤 @_doro1998 每天拆一段 🐾",
    "entertainment": "追蹤 @_doro1998 每天一則娛樂懶人包 🐾",
    "business_finance": "追蹤 @_doro1998ai 每天看懂一個商業模式。非投資建議，請自行查證風險。",
    "finance": "追蹤 @_doro1998ai 每天一則財經懶人包 🐾",
    "pet": "追蹤 @_nailao1998 看奶烙今天又在幹嘛",
    "generic": "追蹤 @_doro1998 每天一則重點懶人包 🐾",
}

YOUTUBE_TAGS_BY_STRATEGY = {
    "tech_judgement": "DORO科技判讀,AI新聞,科技趨勢,AI趨勢,科技解析,人工智慧,ChatGPT,OpenAI,NVIDIA,科技觀點,Doro",
    "tech": "AI新聞,ChatGPT,Claude,Anthropic,AI工具,人工智慧,科技新聞,AI代理,生成式AI,Doro日報,每日AI",
    "tech_tutorial": "AI教學,AI工具,AItips,ChatGPT教學,Claude教學,AI實用,AI技巧,人工智慧應用,Doro日報,學AI",
    "quote_analysis": "名人語錄,AI思維,創業思維,vibecoding,科技觀點,產品思維,AI工作術,創辦人思維,Doro日報,每日觀點",
    "figure_tech": "黃仁勳,張忠謀,科技大咖,AI思維,創業思維,科技觀點,產品思維,AI工作術,Doro日報,名人金句",
    "figure_entertainment": "娛樂咖,名人金句,人生金句,台灣娛樂,訪談精華,明星訪談,娛樂觀點,Doro日報",
    "entertainment": "台灣娛樂,娛樂新聞,熱門話題,YT熱門,電競,電影預告,實況,娛樂懶人包,Doro日報,每日娛樂",
    "business_finance": "商業判讀,商業模式,公司分析,科技財經,財經新聞,市場風險,訂閱制,AI商業,Doro日報,非投資建議",
    "finance": "台股,財經新聞,投資,股市,理財,美股,ETF,財經懶人包,Doro日報,每日財經",
    "pet": "萌寵,寵物日常,貓狗,療癒,可愛動物,pet,寵物頻道,Doro日報",
    "generic": "台灣新聞,每日新聞,熱門話題,新聞懶人包,時事,Doro日報,每日懶人包",
}

FB_PAGE_BY_STRATEGY = {
    "tech_judgement": "1100141579843223",
    "tech": "1100141579843223",
    "tech_tutorial": "1100141579843223",
    "quote_analysis": "1100141579843223",
    "figure_tech": "1100141579843223",
    "figure_entertainment": "1012830001921459",
    "entertainment": "1012830001921459",
    "pet": "1181556318367016",
    "business_finance": "1100141579843223",
    "finance": "1100141579843223",
    "generic": "1012830001921459",
}

HASHTAGS = {
    "tiktok": {
        "tech": "#fyp #AI新聞 #科技新聞 #AI #AItools #Doro日報",
        "tech_tutorial": "#fyp #AI教學 #AI工具 #AItips #學AI #Doro日報",
        "quote_analysis": "#fyp #名人語錄 #AI思維 #創業思維 #vibecoding #Doro日報",
        "figure_tech": "#fyp #科技大咖 #黃仁勳 #AI思維 #創業思維 #Doro日報",
        "figure_entertainment": "#fyp #娛樂咖 #名人金句 #人生金句 #台灣娛樂 #Doro日報",
        "entertainment": "#TikTokTaiwan #台灣娛樂 #娛樂懶人包 #熱搜 #Doro日報 #fyp",
        "business_finance": "#fyp #商業判讀 #商業模式 #財經新聞 #非投資建議 #Doro日報",
        "finance": "#fyp #台股 #財經新聞 #投資 #股市 #Doro日報",
        "pet": "#fyp #萌寵 #寵物日常 #貓狗 #療癒 #Doro日報",
        "generic": "#fyp #每日新聞 #台灣熱搜 #懶人包 #Doro日報 #TikTokTaiwan",
    },
    "instagram": {
        "tech": "#AI新聞 #科技新知 #AI工具 #Doro日報 #台灣科技",
        "tech_tutorial": "#AI教學 #AI工具 #AItips #學AI #Doro日報",
        "quote_analysis": "#名人語錄 #AI思維 #創業思維 #vibecoding #Doro日報",
        "figure_tech": "#科技大咖 #黃仁勳 #AI思維 #創業思維 #Doro日報",
        "figure_entertainment": "#娛樂咖 #名人金句 #人生金句 #台灣娛樂 #Doro日報",
        "entertainment": "#娛樂懶人包 #台灣熱搜 #追劇 #Doro日報 #娛樂圈",
        "business_finance": "#商業判讀 #商業模式 #財經新聞 #科技財經 #非投資建議",
        "finance": "#財經新聞 #台股 #投資理財 #Doro日報 #股市",
        "pet": "#萌寵日常 #寵物 #療癒 #Doro日報 #毛孩",
        "generic": "#台灣新聞 #每日懶人包 #熱搜 #Doro日報 #新聞整理",
    },
    "facebook_body": {
        "tech": "#AI新聞 #科技新知 #AI工具 #台灣科技 #Doro日報",
        "tech_tutorial": "#AI教學 #AI工具 #AItips #學AI #Doro日報",
        "quote_analysis": "#名人語錄 #AI思維 #創業思維 #vibecoding #Doro日報",
        "figure_tech": "#科技大咖 #AI思維 #創業思維 #黃仁勳 #Doro日報",
        "figure_entertainment": "#娛樂咖 #名人金句 #台灣娛樂 #人生金句 #Doro日報",
        "entertainment": "#娛樂新聞 #台灣娛樂 #熱搜話題 #追劇 #Doro日報",
        "business_finance": "#商業判讀 #商業模式 #財經新聞 #科技財經 #非投資建議",
        "finance": "#財經 #投資理財 #台股 #股市 #Doro日報",
        "pet": "#萌寵 #寵物日常 #療癒 #Doro日報",
        "generic": "#每日新聞 #台灣新聞 #熱搜 #懶人包 #Doro日報",
    },
    "threads": {
        "tech": "#AI新聞 #Doro日報",
        "tech_tutorial": "#AI教學 #Doro日報",
        "quote_analysis": "#AI思維 #Doro日報",
        "figure_tech": "#科技大咖 #Doro日報",
        "figure_entertainment": "#娛樂咖 #Doro日報",
        "entertainment": "#娛樂懶人包 #Doro日報",
        "business_finance": "#商業判讀 #非投資建議",
        "finance": "#財經 #Doro日報",
        "pet": "#萌寵 #Doro日報",
        "generic": "#每日新聞 #Doro日報",
    },
    "x": {
        "tech": "#AI #科技 #AINews",
        "tech_tutorial": "#AI #AItips #學AI",
        "quote_analysis": "#AI #名人語錄 #vibecoding",
        "figure_tech": "#AI #科技大咖 #黃仁勳",
        "figure_entertainment": "#娛樂 #名人金句",
        "entertainment": "#娛樂 #熱搜",
        "business_finance": "#商業判讀 #財經",
        "finance": "#台股 #投資",
        "pet": "#萌寵 #寵物",
        "generic": "#新聞 #台灣",
    },
}

HASHTAG_POOLS = {
    "instagram": {
        "tech": ["#AI新聞", "#科技新知", "#AI工具", "#Doro日報", "#台灣科技", "#人工智慧", "#ChatGPT", "#Claude", "#AItools", "#AI懶人包"],
        "quote_analysis": ["#名人語錄", "#AI思維", "#創業思維", "#vibecoding", "#Doro日報", "#科技觀點", "#產品思維", "#工作流"],
        "figure_tech": ["#科技大咖", "#黃仁勳", "#AI思維", "#創業思維", "#Doro日報", "#產品思維", "#AI工作術"],
        "entertainment": ["#娛樂懶人包", "#台灣熱搜", "#追劇", "#Doro日報", "#娛樂圈", "#熱門話題", "#追星"],
        "generic": ["#台灣新聞", "#每日懶人包", "#熱搜", "#Doro日報", "#新聞整理"],
    },
    "facebook_body": {
        "tech": ["#AI新聞", "#科技新知", "#AI工具", "#台灣科技", "#Doro日報", "#ChatGPT", "#Claude"],
        "figure_tech": ["#科技大咖", "#AI思維", "#創業思維", "#黃仁勳", "#Doro日報", "#產品思維"],
        "entertainment": ["#娛樂新聞", "#台灣娛樂", "#熱搜話題", "#追劇", "#Doro日報"],
    },
    "tiktok": {
        "tech": ["#AI新聞", "#科技新聞", "#AI", "#AItools", "#Anthropic", "#人工智慧", "#科技焦點"],
        "figure_tech": ["#科技大咖", "#黃仁勳", "#AI思維", "#創業思維", "#產品思維", "#AI工作術"],
        "quote_analysis": ["#名人語錄", "#AI思維", "#創業思維", "#vibecoding", "#科技觀點"],
        "entertainment": ["#台灣娛樂", "#娛樂懶人包", "#熱搜", "#TikTokTaiwan", "#追劇"],
    },
}

HEADER_POOL = {
    "tech": ["🐾 今日 AI 三件事", "🤖 科技懶人包", "📡 AI 圈動態", "🔥 今日科技焦點"],
    "entertain": ["🐾 今日娛樂三件事", "🎬 今天追什麼", "🔥 今日熱搜", "✨ 娛樂圈三件大事"],
    "pet": ["🐾 奶烙今天在幹嘛", "🐱 今天的貓", "🐾 貓咪日常", "🐱 奶烙小劇場"],
}
SAVE_CTA_POOL = ["📌 收藏起來，這週再翻一次", "🔖 怕忘記就先存", "💾 點儲存留著之後看", "📌 收藏起來，下次喝咖啡再聊"]
CTA_TEMPLATE_POOL = [
    "💬 留言「{kw}」我私訊你{noun} ✨",
    "📩 想看完整版？留言「{kw}」我傳給你",
    "💬 留言「{kw}」幫你整理{noun}",
    "✨ 在留言區打「{kw}」我發{noun}給你",
]
CTA_PHRASING = {
    "tech": ("完整版新聞", "完整版科技新聞", "完整版重點"),
    "entertain": ("完整版懶人包", "完整版娛樂懶人包", "完整版心得"),
}
TECH_CTA_KEYWORDS = ["AI"]


def normalize_strategy(strategy: str | None) -> str:
    strategy = (strategy or "generic").lower().strip()
    return strategy if strategy in STRATEGY_LABEL else "generic"


def strategy_label(strategy: str | None) -> str:
    return STRATEGY_LABEL.get(normalize_strategy(strategy), STRATEGY_LABEL["generic"])


def job_seed(strategy: str, items: list[dict]) -> int:
    key = normalize_strategy(strategy) + "|" + (items[0].get("title", "") if items else "")
    return int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)


def pick(pool: list[str] | tuple[str, ...], seed: int, salt: int = 0) -> str:
    return pool[(seed + salt) % len(pool)] if pool else ""


GENERIC_HOOK_PATTERNS = (
    r"^3\s*(件|個|則)",
    r"^三\s*(件|個|則)",
    r"^先別滑走",
    r"^今日",
    r"^今天",
    r"^科技懶人包",
    r"^AI\s*懶人包",
    r"^DORO",
)


def clean_title_text(text: str, max_len: int = 30) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    text = re.sub(r"https?://\S+", "", text).strip()
    text = re.sub(
        r"\s*[-｜|]\s*(iThome|DIGITIMES|TVBS新聞網|Yahoo新聞|LINE TODAY|電腦王阿達|unwire|T客邦).*$",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(r"\s*-\s*[^-]{2,20}$", "", text).strip()
    return text[:max_len].strip(" ，,。:：｜|-")


def is_generic_hook(text: str) -> bool:
    text = str(text or "").strip()
    if not text:
        return True
    return any(re.search(pattern, text, flags=re.I) for pattern in GENERIC_HOOK_PATTERNS)


def title_angle(item: dict, hook: str) -> str:
    if hook and not is_generic_hook(hook):
        return clean_title_text(hook, 22)
    for key in ("raw_title", "title", "summary"):
        value = clean_title_text(str(item.get(key) or ""), 30)
        if value and not is_generic_hook(value):
            return value
    return clean_title_text(hook or "今日重點", 18)


def resolve_hashtags(platform: str, strategy: str, seed: int, n: int = 5) -> str:
    strategy = normalize_strategy(strategy)
    pool = HASHTAG_POOLS.get(platform, {}).get(strategy)
    if not pool:
        return HASHTAGS[platform].get(strategy, HASHTAGS[platform]["generic"])
    start = seed % len(pool)
    return " ".join(pool[(start + i) % len(pool)] for i in range(min(n, len(pool))))


def resolve_tiktok_hashline(strategy: str, seed: int) -> str:
    strategy = normalize_strategy(strategy)
    pool = HASHTAG_POOLS.get("tiktok", {}).get(strategy)
    if not pool:
        return HASHTAGS["tiktok"].get(strategy, HASHTAGS["tiktok"]["generic"])
    start = seed % len(pool)
    middle = [pool[(start + i) % len(pool)] for i in range(min(3, len(pool)))]
    return " ".join(["#fyp", *middle, "#Doro日報"])


def compose_title(hooks: list[str], items: list[dict], strategy: str) -> str:
    strategy = normalize_strategy(strategy)
    first_item = items[0] if items and isinstance(items[0], dict) else {}
    first_hook = title_angle(first_item, str(hooks[0] if hooks else ""))
    n = len([h for h in hooks if h])
    return TITLE_FORMULA[strategy].format(hook=first_hook, n=max(n, 1))[:100]


def strategy_cta_keyword(strategy: str, seed: int = 0, get_setting: Callable[[str, str], str] | None = None) -> str:
    strategy = normalize_strategy(strategy)
    group = STRATEGY_CTA_GROUP.get(strategy, "entertain")
    if group == "tech":
        return "AI"
    if get_setting:
        return (get_setting(f"cta_kw_{group}", "今日娛樂") or "今日娛樂").strip()
    return "今日娛樂"


def strategy_uses_manychat_cta(
    strategy: str,
    get_setting: Callable[[str, str], str] | None = None,
) -> bool:
    """Only promise DM resources when the ManyChat funnel is actually enabled.

    Entertainment, pet, and the experimental storyboard lane must not ask
    viewers to comment for a resource that does not exist. The setting defaults
    to false until the Doro tech account's backend content/DM flow is ready.
    """
    strategy = normalize_strategy(strategy)
    if strategy not in MANYCHAT_CTA_STRATEGIES:
        return False
    if not get_setting:
        return False
    enabled = str(get_setting("manychat_cta_enabled", "false") or "false").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return False
    allowed = str(get_setting("manychat_cta_strategies", ",".join(sorted(MANYCHAT_CTA_STRATEGIES))) or "")
    allowed_set = {s.strip().lower() for s in re.split(r"[,\s]+", allowed) if s.strip()}
    return strategy in allowed_set


def strategy_cta_line(strategy: str, seed: int = 0, get_setting: Callable[[str, str], str] | None = None) -> str:
    if not strategy_uses_manychat_cta(strategy, get_setting=get_setting):
        return ""
    strategy = normalize_strategy(strategy)
    group = STRATEGY_CTA_GROUP.get(strategy, "entertain")
    noun = pick(CTA_PHRASING.get(group, CTA_PHRASING["entertain"]), seed, salt=7)
    template = pick(CTA_TEMPLATE_POOL, seed, salt=13)
    kw = strategy_cta_keyword(strategy, seed=seed, get_setting=get_setting)
    return template.format(kw=kw, noun=noun)


def compose_description(
    items: list[dict],
    strategy: str,
    signoff: bool = True,
    get_setting: Callable[[str, str], str] | None = None,
) -> str:
    strategy = normalize_strategy(strategy)
    if not items:
        return SIGNOFF[strategy]
    seed = job_seed(strategy, items)
    group = STRATEGY_CTA_GROUP.get(strategy, "entertain")
    header = pick(HEADER_POOL.get(group, HEADER_POOL["entertain"]), seed, salt=3)
    lines = []
    for i, item in enumerate(items, 1):
        hook = item.get("hook") or ""
        title = item.get("title") or ""
        script = (item.get("script") or item.get("summary") or "")[:80]
        marker = "①②③④⑤"[i - 1] if i <= 5 else f"{i}."
        lines.append(f"{marker} {hook}：{title}")
        if script:
            lines.append(f"    {script}")
    body = "\n".join(lines)
    if not signoff:
        return f"{header}\n\n{body}"
    cta = strategy_cta_line(strategy, seed=seed, get_setting=get_setting)
    cta_block = f"\n\n{cta}" if cta else ""
    return (
        f"{header}\n\n{body}"
        f"{cta_block}"
        f"\n{pick(SAVE_CTA_POOL, seed, salt=17)}"
        f"\n{SIGNOFF[strategy]}"
    )


def build_basic_metadata(items: list[dict], strategy: str = "tech") -> dict:
    """Fallback title/description for publisher when platform_meta is missing."""
    strategy = normalize_strategy(strategy)
    hooks = [str(item.get("hook") or item.get("title") or "") for item in items]
    title = compose_title(hooks, items, strategy)
    description = compose_description(items, strategy, signoff=True)
    hashtags = HASHTAGS["instagram"].get(strategy, HASHTAGS["instagram"]["generic"])
    return {"title": title, "description": f"{description}\n\n{hashtags}"}


def seed_platform_meta(news: dict, get_setting: Callable[[str, str], str] | None = None) -> dict:
    items = news.get("items", []) or []
    strategy = normalize_strategy(news.get("strategy"))
    hooks = [item.get("hook", "") for item in items] if items else [""]
    main_title = compose_title(hooks, items, strategy)
    long_desc = compose_description(items, strategy, signoff=True, get_setting=get_setting)
    seed = job_seed(strategy, items)

    def tags(platform: str, n: int = 5) -> str:
        if platform == "tiktok":
            return resolve_tiktok_hashline(strategy, seed)
        return resolve_hashtags(platform, strategy, seed, n=n)

    cta_line = strategy_cta_line(strategy, seed=seed, get_setting=get_setting)
    instagram_first_comment = (
        f"{cta_line}\n\n{tags('instagram')}" if cta_line else tags("instagram")
    )

    yt_tags_csv = YOUTUBE_TAGS_BY_STRATEGY.get(strategy, YOUTUBE_TAGS_BY_STRATEGY["generic"])
    is_aigc = IS_AIGC_BY_STRATEGY.get(strategy, True)
    fb_page_id = FB_PAGE_BY_STRATEGY.get(strategy, FB_PAGE_BY_STRATEGY["generic"])
    tech_judgement_short_only = strategy == "tech_judgement"
    youtube_x_version = "short" if tech_judgement_short_only else "long"
    use_youtube_cover = not tech_judgement_short_only
    use_social_cover = True
    schedule_offset_hours = 0
    if isinstance(news.get("media_ops_schedule_offset_hours"), (int, float, str)):
        try:
            schedule_offset_hours = max(0, min(6, int(news.get("media_ops_schedule_offset_hours") or 0)))
        except (TypeError, ValueError):
            schedule_offset_hours = 0
    elif items and isinstance(items[0], dict):
        try:
            schedule_offset_hours = max(0, min(6, int(items[0].get("media_ops_schedule_offset_hours") or 0)))
        except (TypeError, ValueError):
            schedule_offset_hours = 0

    return {
        "youtube": {
            "video_version": youtube_x_version,
            "title": main_title,
            "description": long_desc,
            "tags": yt_tags_csv,
            "use_auto_thumbnail": use_youtube_cover,
            "categoryId": "22",
            "defaultLanguage": "zh-TW",
            "defaultAudioLanguage": "zh-TW",
            "privacyStatus": "public",
            "containsSyntheticMedia": True,
            "selfDeclaredMadeForKids": False,
            "embeddable": True,
            "publicStatsViewable": True,
            "license": "youtube",
        },
        "tiktok": {
            "video_version": "short" if tech_judgement_short_only else "long",
            "title": f"{main_title}\n\n{tags('tiktok')}",
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "is_aigc": is_aigc,
            "cover_timestamp": 1000,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
            "brand_content_toggle": False,
            "brand_organic_toggle": False,
        },
        "instagram": {
            "video_version": "short",
            "use_auto_thumbnail": use_social_cover,
            "title": long_desc,
            "first_comment": instagram_first_comment,
            "share_mode": "REELS",
            "share_to_feed": True,
            "collaborators": "",
            "user_tags": "",
        },
        "facebook": {
            "video_version": "short",
            "title": main_title,
            "description": f"{long_desc}\n\n{tags('facebook_body')}",
            "facebook_media_type": "REELS",
            "video_state": "PUBLISHED",
            "facebook_page_id": fb_page_id,
        },
        "threads": {"video_version": "short", "title": f"{main_title[:400]}\n{tags('threads')}", "threads_topic_tag": ""},
        "x": {"video_version": youtube_x_version, "title": f"{main_title[:240]} {tags('x')}"[:280], "poll_options": "", "poll_duration": 1440, "reply_settings": "everyone", "x_long_text_as_post": False},
        "linkedin": {"video_version": "short" if tech_judgement_short_only else "long", "title": main_title, "description": long_desc, "visibility": "PUBLIC", "target_linkedin_page_id": ""},
        "_schedule": {
            "mode": "auto_per_platform",
            "scheduled_date": "",
            "timezone": "Asia/Taipei",
            "media_ops_offset_hours": schedule_offset_hours,
        },
    }


def youtube_tags_list(strategy: str) -> list[str]:
    tags = YOUTUBE_TAGS_BY_STRATEGY.get(normalize_strategy(strategy), YOUTUBE_TAGS_BY_STRATEGY["generic"])
    return [tag.strip() for tag in re.split(r"[,\uff0c\u3001\n]+", tags) if tag.strip()]
