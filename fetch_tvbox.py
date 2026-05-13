# fetch_tvbox.py
import requests
import json
import os

GITHUB_USER = "luckyprc"
GITHUB_REPO = "tvbox"
MAX_SOURCES = 10
API_URL = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents"

def fetch_json_files(path=""):
    """
    递归抓取所有 JSON 文件
    """
    url = f"{API_URL}/{path}" if path else API_URL
    response = requests.get(url)
    response.raise_for_status()
    items = response.json()

    json_files = []

    for item in items:
        if item['type'] == 'file' and item['name'].endswith('.json'):
            file_url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/{item['path']}"
            # 获取最后提交时间
            commits_url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/commits?path={item['path']}&per_page=1"
            r = requests.get(commits_url)
            r.raise_for_status()
            commit_data = r.json()
            last_update = commit_data[0]['commit']['committer']['date'] if commit_data else ""
            json_files.append({
                "name": item['path'],
                "url": file_url,
                "last_update": last_update
            })
        elif item['type'] == 'dir':
            # 递归子目录
            json_files.extend(fetch_json_files(item['path']))

    return json_files

def save_list(sources):
    list_path = os.path.join(os.getcwd(), "list.json")
    with open(list_path, "w", encoding="utf-8") as f:
        json.dump(sources, f, ensure_ascii=False, indent=2)
    print(f"✅ list.json 已生成: {list_path}")

def main():
    try:
        sources = fetch_json_files()
        if not sources:
            print("⚠️ 没有找到匹配的 JSON 文件。")
            return
        # 按更新时间降序取最新10个
        sources.sort(key=lambda x: x['last_update'], reverse=True)
        sources = sources[:MAX_SOURCES]
        save_list(sources)
    except requests.HTTPError as e:
        print(f"HTTP Error: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
