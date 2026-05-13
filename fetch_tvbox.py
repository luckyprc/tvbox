import requests
import json
import os

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
MAX_SOURCES = 50          # 总共最多收录多少个源
MAX_PER_REPO = 8          # 每个仓库最多取几个文件（防止 gaotianliuyun/gao 这种文件爆炸的仓库拖垮）

# ============================================
# TARGET_REPOS 配置说明：
# (用户名, 仓库名, 子目录, 文件名过滤)
# 子目录为空 = 扫描整个仓库
# 文件名过滤为空 = 不过滤
# ============================================
TARGET_REPOS = [
    # --- 核心配置仓库（文件多、更新频繁）---
    ("gaotianliuyun", "gao", "", ".json"),          # 高天流云：0821/0825/0827/js.json 等
    ("qist", "tvbox", "", ".json"),                 # qist：jsm.json / 0821.json 等
    ("liu673cn", "box", "", ".json"),               # liu673cn：m.json
    ("yoursmile66", "TVBox", "", ".json"),           # Yoursmile：XC.json

    # --- 特色源仓库 ---
    ("xyq254245", "xyqonlinerule", "", ".json"),     # 香雅情：XYQTVBox.json
    ("tushen6", "Tomorrow", "", ".json"),            # 土神：tvbox.json / lmw.json
    ("kebedd69", "TVbox-interface", "", ".json"),  # 甜蜜接口
    ("xianyuyimu", "TVBOX-", "", ".json"),           # 一木自用
    ("XiaoYiChaHang", "tvbox", "", ".json"),         # 小易茶馆：ysj.json
    ("lm317379829", "PyramidStore", "", ".json"),    # Pyramid：py.json
    ("tv-player", "tvbox-line", "", ".json"),         # tvbox-line：fj.json
    ("dxawi", "0", "", ".json"),                     # dxawi：0.json
    ("Yosakoii", "Yosakoii.github.io", "", ".json"),  # Yosakoii：2023.json
    ("hanhan8127", "TVBox", "", ".json"),            # hanhan：hanXC.json
    ("jigedos", "1024", "", ".json"),                # jigedos：jsm.json
    ("UndCover", "PyramidStore", "", ".json"),        # UndCover：py.json
    ("leevi0709", "one", "", ".json"),               # leevi：jsm.json
    ("franksun1211", "TVBOX", "", ".json"),          # franksun：fuli.json
    ("Newtxin", "tvbox", "", ".json"),               # Newtxin：2.json
    ("hy5528", "tvbox", "", ".json"),                # hy5528：my.json
    ("FongMi", "TV", "", ".json"),                   # FongMi 官方：tv.json

    # --- 直播源仓库 ---
    ("Guovin", "iptv-api", "gd/output", ""),         # IPTV 直播源（result.m3u / result.txt）
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
    """获取仓库默认分支（main 还是 master）"""
    url = f"https://api.github.com/repos/{user}/{repo}"
    try:
        r = requests.get(url, headers=get_headers(), timeout=30)
        r.raise_for_status()
        return r.json().get("default_branch", "main")
    except Exception as e:
        print(f"     ⚠️ 无法获取分支，默认用 main: {e}")
        return "main"


def fetch_contents(user, repo, path="", branch="main"):
    """获取仓库目录内容"""
    encoded_path = requests.utils.quote(path, safe="") if path else ""
    url = f"https://api.github.com/repos/{user}/{repo}/contents/{encoded_path}?ref={branch}"
    if not path:
        url = url.replace("/contents/?", "/contents?")
    try:
        r = requests.get(url, headers=get_headers(), timeout=30)
        if r.status_code == 404:
            print(f"     ⚠️ 路径不存在: {user}/{repo}/{path} (branch={branch})")
            return []
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"     ❌ 请求失败: {e}")
        return []


def find_json_files(user, repo, path="", name_filter="", branch="main", max_depth=3, current_depth=0):
    """递归查找 .json / .txt 文件"""
    if current_depth >= max_depth:
        return []

    items = fetch_contents(user, repo, path, branch)
    results = []

    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "file":
            name = item["name"]
            # 支持 .json 和 .txt（有些源是 txt 格式）
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


def validate_source(url):
    """验证文件是否能正常下载"""
    try:
        r = requests.get(url, headers={"User-Agent": "TVBox-Fetcher"}, timeout=30)
        r.raise_for_status()
        # txt 文件直接通过；json 文件尝试解析
        if url.endswith(".txt"):
            return True
        r.json()
        return True
    except Exception:
        return False


def main():
    if not TARGET_REPOS:
        print("⚠️ TARGET_REPOS 为空，请在脚本里配置目标仓库")
        return

    all_sources = []

    for user, repo, subdir, name_filter in TARGET_REPOS:
        print(f"\n🔍 扫描 {user}/{repo} ...")
        branch = get_default_branch(user, repo)
        files = find_json_files(user, repo, subdir, name_filter, branch)

        # 限制每个仓库的文件数，防止个别仓库文件过多拖垮
        files = files[:MAX_PER_REPO]

        for f in files:
            print(f"  📄 {f['path']} ({f['size']} bytes)")
            if validate_source(f["url"]):
                # 获取最后提交时间
                commits_url = (
                    f"https://api.github.com/repos/{user}/{repo}/commits"
                    f"?path={requests.utils.quote(f['path'], safe='')}&per_page=1"
                )
                try:
                    cr = requests.get(commits_url, headers=get_headers(), timeout=30)
                    cr.raise_for_status()
                    commits = cr.json()
                    last_update = commits[0]["commit"]["committer"]["date"] if commits else ""
                except Exception:
                    last_update = ""

                all_sources.append({
                    "name": f["name"],
                    "repo": f["repo"],
                    "path": f["path"],
                    "url": f["url"],
                    "size": f["size"],
                    "last_update": last_update
                })
                print(f"     ✅ 有效")
            else:
                print(f"     ❌ 验证失败，跳过")

        if len(all_sources) >= MAX_SOURCES:
            print(f"⏹️ 已达到最大源数限制 ({MAX_SOURCES})，停止扫描")
            break

    if not all_sources:
        print("\n⚠️ 未找到有效源，不生成 list.json")
        return

    # 按更新时间倒序
    all_sources.sort(key=lambda x: x.get("last_update", ""), reverse=True)
    all_sources = all_sources[:MAX_SOURCES]

    # 生成 list.json
    output = {
        "update_time": "",
        "total": len(all_sources),
        "sources": all_sources
    }

    with open("list.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ list.json 已生成，共 {len(all_sources)} 个源")


if __name__ == "__main__":
    main()
