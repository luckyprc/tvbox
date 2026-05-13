import requests
import json
from datetime import datetime

# -----------------------------
# 配置参数
# -----------------------------
search_query = "tvbox json"
max_search_results = 20  # 搜索最多文件数，保证可以挑出最新10个
top_n = 10               # 最终保留最新10个
github_token = None       # 可选：GitHub Token

headers = {}
if github_token:
    headers['Authorization'] = f'token {github_token}'

# -----------------------------
# 1️⃣ 搜索 GitHub 文件
# -----------------------------
search_url = f"https://api.github.com/search/code?q={search_query}&per_page={max_search_results}"
search_resp = requests.get(search_url, headers=headers)
search_data = search_resp.json()

files = search_data.get('items', [])
if not files:
    print("没有找到匹配的 JSON 文件。")
    exit()

tvbox_list = []

# -----------------------------
# 2️⃣ 获取每个文件的最新提交
# -----------------------------
for file in files:
    repo_full_name = file['repository']['full_name']
    file_path = file['path']
    branch = file['repository']['default_branch']

    # 获取最新提交
    commits_url = f"https://api.github.com/repos/{repo_full_name}/commits?path={file_path}&per_page=1"
    commits_resp = requests.get(commits_url, headers=headers)
    commits = commits_resp.json()
    if not commits:
        continue

    latest_commit = commits[0]
    commit_date = latest_commit['commit']['author']['date']

    # 下载 JSON 文件内容
    raw_url = f"https://raw.githubusercontent.com/{repo_full_name}/{branch}/{file_path}"
    json_resp = requests.get(raw_url)
    try:
        json_data = json_resp.json()
    except:
        continue

    tvbox_list.append({
        "repo": repo_full_name,
        "path": file_path,
        "branch": branch,
        "last_update": commit_date,
        "raw_url": raw_url,
        "data_preview": json_data[:3] if isinstance(json_data, list) else json_data
    })

# -----------------------------
# 3️⃣ 按最近更新时间排序，取最新10个
# -----------------------------
tvbox_list.sort(key=lambda x: datetime.strptime(x['last_update'], "%Y-%m-%dT%H:%M:%SZ"), reverse=True)
latest_10 = tvbox_list[:top_n]

# -----------------------------
# 4️⃣ 写入 list.json
# -----------------------------
with open("list.json", "w", encoding="utf-8") as f:
    json.dump(latest_10, f, ensure_ascii=False, indent=2)

print(f"成功抓取 {len(latest_10)} 个最新 TVBox 源到 list.json")
