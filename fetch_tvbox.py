import requests
import json
import os
import re
from urllib.parse import urlparse

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
MAX_SOURCES = 30          # 扫描时最多处理多少个源
MAX_PER_REPO = 8          # 每个仓库最多取几个文件

TARGET_REPOS = [
    ("gaotianliuyun", "gao", "", ".json"),
    ("qist", "tvbox", "", ".json"),
    ("liu673cn", "box", "", ".json"),
    ("yoursmile66", "TVBox", "", ".json"),
    ("xyq254245", "xyqonlinerule", "", ".json"),
    ("tushen6", "Tomorrow", "", ".json"),
    ("kebedd69", "TVbox-interface", "", ".json"),
    ("xianyuyimu", "TVBOX-", "", ".json"),
    ("XiaoYiChaHang", "tvbox", "", ".json"),
    ("lm317379829", "PyramidStore", "", ".json"),
    ("tv-player", "tvbox-line", "", ".json"),
    ("dxawi", "0", "", ".json"),
    ("Yosakoii", "Yosakoii.github.io", "", ".json"),
    ("hanhan8127", "TVBox", "", ".json"),
    ("jigedos", "1024", "", ".json"),
    ("UndCover", "PyramidStore", "", ".json"),
    ("leevi0709", "one", "", ".json"),
    ("franksun1211", "TVBOX", "", ".json"),
    ("Newtxin", "tvbox", "", ".json"),
    ("hy5528", "tvbox", "", ".json"),
    ("FongMi", "TV", "", ".json"),
]

# 广告关键词（用于过滤站点和解析接口）
AD_KEYWORDS = [
    "广告", "推广", "公告", "购物", "商城", "彩票", "博彩", "投注",
    "ad", "advert", "ads", "shopping", "mall", "lottery", "bet",
    "banner", "popup", "推广", "营销", "affiliate", "赚钱", "返利",
    "任务", "签到", "积分", "vip", "会员", "充值", "支付"
]

# 强制加入的广告拦截规则
AD_BLOCK_RULES = [
    {"host": "*", "rule": ["/ad/", "/ads/", "ad.js", "advert", "googlead", "googlesyndication"]},
    {"host": "*", "rule": [".jpg", ".png", ".gif"]},
    {"host": "miguvideo", "rule": [".mp4"]},
    {"host": "*", "rule": ["vip.ffzy", "vip.lz", "vip.ffzy", "ad.zt", "cdn.zycami"]},
]


def get_headers():
    h = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "TVBox-Fetcher"
    }
    if GITHUB_TOKEN:
        h["Authorization"] = f"token {GITHUB_TOKEN}"
    return h


def get_default_branch(user, repo):
    url = f"https://api.github.com/repos/{user}/{repo}"
    try:
        r = requests.get(url, headers=get_headers(), timeout=30)
        r.raise_for_status()
        return r.json().get("default_branch", "main")
    except Exception as e:
        print(f"     ⚠️ 无法获取分支，默认用 main: {e}")
        return "main"


def fetch_contents(user, repo, path="", branch="main"):
    encoded_path = requests.utils.quote(path, safe="") if path else ""
    url = f"https://api.github.com/repos/{user}/{repo}/contents/{encoded_path}?ref={branch}"
    if not path:
        url = url.replace("/contents/?", "/contents?")
    try:
        r = requests.get(url, headers=get_headers(), timeout=30)
        if r.status_code == 404:
            return []
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"     ❌ 请求失败: {e}")
        return []


def find_json_files(user, repo, path="", name_filter="", branch="main", max_depth=3, current_depth=0):
    if current_depth >= max_depth:
        return []
    items = fetch_contents(user, repo, path, branch)
    results = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "file":
            name = item["name"]
            if name.endswith(".json") or name.endswith(".txt"):
                if name_filter and name_filter not in name:
                    continue
                raw_url = f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{item['path']}"
                results.append({
                    "name": name,
                    "repo": f"{user}/{repo}",
                    "path": item["path"],
                    "url": raw_url,
                    "size": item.get("size", 0)
                })
        elif item.get("type") == "dir":
            results.extend(
                find_json_files(user, repo, item["path"], name_filter, branch, max_depth, current_depth + 1)
            )
    return results


def fetch_source_content(url):
    """下载源的实际内容"""
    try:
        r = requests.get(url, headers={"User-Agent": "TVBox-Fetcher"}, timeout=30)
        r.raise_for_status()
        if url.endswith(".txt"):
            try:
                return r.json()
            except:
                return None
        return r.json()
    except Exception as e:
        print(f"     ❌ 下载失败: {e}")
        return None


def is_ad_site(site):
    """判断站点是否是广告"""
    if not isinstance(site, dict):
        return True
    name = str(site.get("name", "")).lower()
    key = str(site.get("key", "")).lower()
    api = str(site.get("api", "")).lower()
    ext = str(site.get("ext", "")).lower()

    for kw in AD_KEYWORDS:
        kw_lower = kw.lower()
        if kw_lower in name or kw_lower in key or kw_lower in api or kw_lower in ext:
            return True
    return False


def is_ad_parse(parse):
    """判断解析接口是否是广告"""
    if not isinstance(parse, dict):
        return True
    name = str(parse.get("name", "")).lower()
    url = str(parse.get("url", "")).lower()
    for kw in AD_KEYWORDS:
        if kw.lower() in name or kw.lower() in url:
            return True
    return False


def merge_sources(contents_list):
    """合并多个 TVBox 源，去广告"""
    merged = {
        "spider": "",
        "wallpaper": "",
        "lives": [],
        "sites": [],
        "parses": [],
        "rules": [],
    }

    seen_sites = set()
    seen_parses = set()
    seen_lives = set()
    seen_rules = set()

    for content in contents_list:
        if not isinstance(content, dict):
            continue

        # spider：保留第一个非空的
        if not merged["spider"] and content.get("spider"):
            merged["spider"] = content["spider"]

        if not merged["wallpaper"] and content.get("wallpaper"):
            merged["wallpaper"] = content["wallpaper"]

        # 合并 sites（去广告 + 按 key 去重）
        for site in content.get("sites", []):
            if is_ad_site(site):
                continue
            key = site.get("key", "")
            if key:
                if key in seen_sites:
                    continue
                seen_sites.add(key)
            else:
                # 无 key 的站点按 name+api 去重
                sig = f"{site.get('name','')}|{site.get('api','')}"
                if sig in seen_sites:
                    continue
                seen_sites.add(sig)
            merged["sites"].append(site)

        # 合并 parses（去广告 + 按 name+url 去重）
        for parse in content.get("parses", []):
            if is_ad_parse(parse):
                continue
            name = parse.get("name", "")
            url = parse.get("url", "")
            sig = f"{name}|{url}"
            if sig in seen_parses:
                continue
            seen_parses.add(sig)
            merged["parses"].append(parse)

        # 合并 lives（按 name+url 去重）
        for live in content.get("lives", []):
            if not isinstance(live, dict):
                continue
            name = live.get("name", "")
            url = live.get("url", "")
            sig = f"{name}|{url}"
            if sig in seen_lives:
                continue
            seen_lives.add(sig)
            merged["lives"].append(live)

        # 合并 rules
        for rule in content.get("rules", []):
            if not isinstance(rule, dict):
                continue
            host = rule.get("host", "")
            rule_list = rule.get("rule", [])
            sig = f"{host}|{json.dumps(rule_list, sort_keys=True)}"
            if sig in seen_rules:
                continue
            seen_rules.add(sig)
            merged["rules"].append(rule)

    # 强制加入广告拦截规则
    for ad_rule in AD_BLOCK_RULES:
        sig = f"{ad_rule['host']}|{json.dumps(ad_rule['rule'], sort_keys=True)}"
        if sig not in seen_rules:
            merged["rules"].append(ad_rule)
            seen_rules.add(sig)

    # 清理空字段
    for key in list(merged.keys()):
        if not merged[key]:
            del merged[key]

    return merged


def main():
    if not TARGET_REPOS:
        print("⚠️ TARGET_REPOS 为空")
        return

    all_sources = []

    # 第一步：扫描仓库获取源 URL 列表
    for user, repo, subdir, name_filter in TARGET_REPOS:
        print(f"\n🔍 扫描 {user}/{repo} ...")
        branch = get_default_branch(user, repo)
        files = find_json_files(user, repo, subdir, name_filter, branch)
        files = files[:MAX_PER_REPO]

        for f in files:
            print(f"  📄 {f['path']}")
            all_sources.append(f)

        if len(all_sources) >= MAX_SOURCES:
            print(f"⏹️ 达到上限，停止扫描")
            break

    if not all_sources:
        print("\n⚠️ 未找到源")
        return

    print(f"\n📥 开始下载 {len(all_sources)} 个源的内容...")

    # 第二步：下载每个源的实际内容
    contents = []
    for src in all_sources:
        print(f"  ⬇️ {src['repo']} - {src['name']}")
        content = fetch_source_content(src["url"])
        if content:
            contents.append(content)
            print(f"     ✅ 成功")
        else:
            print(f"     ❌ 失败")

    if not contents:
        print("\n⚠️ 没有成功下载的源")
        return

    print(f"\n🔀 合并 {len(contents)} 个源，去广告...")
    merged = merge_sources(contents)

    # 生成聚合文件
    with open("tvbox_merged.json", "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    # 同时生成 list.json（索引）
    list_data = {
        "update_time": "",
        "total": len(all_sources),
        "sources": all_sources
    }
    with open("list.json", "w", encoding="utf-8") as f:
        json.dump(list_data, f, ensure_ascii=False, indent=2)

    site_count = len(merged.get("sites", []))
    parse_count = len(merged.get("parses", []))
    live_count = len(merged.get("lives", []))
    rule_count = len(merged.get("rules", []))

    print(f"\n✅ 生成完成:")
    print(f"   - tvbox_merged.json: 聚合源 ({site_count} 站点, {parse_count} 解析, {live_count} 直播, {rule_count} 规则)")
    print(f"   - list.json: 源索引 ({len(all_sources)} 个)")


if __name__ == "__main__":
    main()
