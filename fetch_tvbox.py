import requests
import json
import os
from urllib.parse import quote

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
MAX_SOURCES = 30
MAX_PER_REPO = 8

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

AD_KEYWORDS = [
    "广告", "推广", "公告", "购物", "商城", "彩票", "博彩", "投注",
    "ad", "advert", "ads", "shopping", "mall", "lottery", "bet",
    "banner", "popup", "推广", "营销", "affiliate", "赚钱", "返利",
    "任务", "签到", "积分", "vip", "会员", "充值", "支付"
]

AD_BLOCK_RULES = [
    {"host": "*", "rule": ["/ad/", "/ads/", "ad.js", "advert", "googlead", "googlesyndication"]},
    {"host": "*", "rule": [".jpg", ".png", ".gif"]},
    {"host": "miguvideo", "rule": [".mp4"]},
    {"host": "*", "rule": ["vip.ffzy", "vip.lz", "ad.zt", "cdn.zycami"]},
]

def get_headers():
    h = {"Accept": "application/vnd.github.v3+json", "User-Agent": "TVBox-Fetcher"}
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
                results.append({"name": name, "repo": f"{user}/{repo}", "path": item["path"], "url": raw_url, "size": item.get("size", 0)})
        elif item.get("type") == "dir":
            results.extend(find_json_files(user, repo, item["path"], name_filter, branch, max_depth, current_depth + 1))
    return results

def fetch_source_content(url):
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
    if not isinstance(site, dict):
        return True
    name = str(site.get("name", "")).lower()
    key = str(site.get("key", "")).lower()
    api = str(site.get("api", "")).lower()
    ext = str(site.get("ext", "")).lower()
    for kw in AD_KEYWORDS:
        if kw.lower() in name or kw.lower() in key or kw.lower() in api or kw.lower() in ext:
            return True
    return False

def is_ad_parse(parse):
    if not isinstance(parse, dict):
        return True
    name = str(parse.get("name", "")).lower()
    url = str(parse.get("url", "")).lower()
    for kw in AD_KEYWORDS:
        if kw.lower() in name or kw.lower() in url:
            return True
    return False

def merge_sources(contents_list):
    merged = {"spider": "", "wallpaper": "", "lives": [], "sites": [], "parses": [], "rules": []}
    seen_sites = set()
    seen_parses = set()
    seen_lives = set()
    seen_rules = set()
    for content in contents_list:
        if not isinstance(content, dict):
            continue
        if not merged["spider"] and content.get("spider"):
            merged["spider"] = content["spider"]
        if not merged["wallpaper"] and content.get("wallpaper"):
            merged["wallpaper"] = content["wallpaper"]
        for site in content.get("sites", []):
            if is_ad_site(site):
                continue
            key = site.get("key", "")
            if key:
                if key in seen_sites:
                    continue
                seen_sites.add(key)
            else:
                sig = f"{site.get('name','')}|{site.get('api','')}"
                if sig in seen_sites:
                    continue
                seen_sites.add(sig)
            merged["sites"].append(site)
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
    for ad_rule in AD_BLOCK_RULES:
        sig = f"{ad_rule['host']}|{json.dumps(ad_rule['rule'], sort_keys=True)}"
        if sig not in seen_rules:
            merged["rules"].append(ad_rule)
            seen_rules.add(sig)
    for key in list(merged.keys()):
        if not merged[key]:
            del merged[key]
    return merged


def generate_index_html(sources, merged_info):
    rows = []
    for i, s in enumerate(sources, 1):
        rows.append(f"    <tr><td>{i}</td><td>{s['name']}</td><td>{s['repo']}</td><td><a href='{s['url']}' target='_blank'>raw</a></td></tr>")
    rows_str = "\n".join(rows)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TVBox 聚合源</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; background: #f5f5f5; }}
h1 {{ color: #333; }}
.card {{ background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
.btn {{ display: inline-block; padding: 10px 20px; margin: 5px; background: #0366d6; color: #fff; text-decoration: none; border-radius: 5px; font-size: 14px; }}
.btn:hover {{ background: #0256c7; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #eee; }}
th {{ background: #f8f9fa; font-weight: 600; }}
a {{ color: #0366d6; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.stats {{ display: flex; gap: 20px; flex-wrap: wrap; }}
.stat {{ background: #e3f2fd; padding: 10px 15px; border-radius: 5px; }}
.stat strong {{ color: #0366d6; font-size: 18px; }}
code {{ background:#f4f4f4; padding:8px 12px; border-radius:4px; display:block; word-break:break-all; margin:10px 0; }}
</style>
</head>
<body>
<h1>TVBox 聚合源</h1>
<div class="card">
<h2>快速使用</h2>
<p>复制以下地址到 TVBox 配置地址栏：</p>
<code>https://luckyprc.github.io/tvbox/tvbox_merged.json</code>
<div>
<a class="btn" href="tvbox_merged.json" target="_blank">打开聚合源</a>
<a class="btn" href="list.json" target="_blank">源索引</a>
</div>
</div>
<div class="card">
<h2>聚合统计</h2>
<div class="stats">
<div class="stat">站点 <strong>{merged_info.get('sites', 0)}</strong></div>
<div class="stat">解析 <strong>{merged_info.get('parses', 0)}</strong></div>
<div class="stat">直播 <strong>{merged_info.get('lives', 0)}</strong></div>
<div class="stat">规则 <strong>{merged_info.get('rules', 0)}</strong></div>
<div class="stat">来源 <strong>{merged_info.get('sources', 0)}</strong></div>
</div>
</div>
<div class="card">
<h2>原始源列表</h2>
<table>
<thead><tr><th>#</th><th>文件名</th><th>仓库</th><th>链接</th></tr></thead>
<tbody>
{rows_str}
</tbody>
</table>
</div>
<div class="card" style="text-align:center;color:#666;font-size:12px;">
自动更新 · 去广告 · 聚合 {merged_info.get('sources', 0)} 个源
</div>
</body>
</html>"""
    return html

def main():
    if not TARGET_REPOS:
        print("⚠️ TARGET_REPOS 为空")
        return
    all_sources = []
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
    with open("tvbox_merged.json", "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    list_data = {"update_time": "", "total": len(all_sources), "sources": all_sources}
    with open("list.json", "w", encoding="utf-8") as f:
        json.dump(list_data, f, ensure_ascii=False, indent=2)
    merged_info = {
        "sites": len(merged.get("sites", [])),
        "parses": len(merged.get("parses", [])),
        "lives": len(merged.get("lives", [])),
        "rules": len(merged.get("rules", [])),
        "sources": len(all_sources)
    }
    html = generate_index_html(all_sources, merged_info)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✅ 生成完成:")
    print(f"   - tvbox_merged.json: 聚合源")
    print(f"   - list.json: 源索引 ({len(all_sources)} 个)")
    print(f"   - index.html: 导航页")
    print(f"   站点:{merged_info['sites']} 解析:{merged_info['parses']} 直播:{merged_info['lives']} 规则:{merged_info['rules']}")

if __name__ == "__main__":
    main()