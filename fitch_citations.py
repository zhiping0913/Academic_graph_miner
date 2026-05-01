
import time
import requests
import argparse
import sys
from datetime import datetime

from db_sqlite import load_db, upsert_paper, get_paper, is_expired

# --- 核心配置 ---
S2_API_URL = "https://api.semanticscholar.org/graph/v1/paper/DOI:"
CR_API_URL = "https://api.crossref.org/works/"
OC_CITATIONS_URL = "https://opencitations.net/index/coci/api/v1/citations/"
OC_REFERENCES_URL = "https://opencitations.net/index/coci/api/v1/references/"

# --- 算法参数 ---
THRESHOLD = 0.1          # Jaccard 相似度阈值
MAX_DEPTH = 2            # 最大探索深度
UPDATE_DAYS = 1000         # 数据更新周期天数
REQUEST_DELAY = 1.2      # API 限制间隔

# 模拟浏览器 Headers，防止被部分 API 节点拦截
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json'
}


def fetch_semanticscholar(doi):
    """
    从 Semantic Scholar API 获取论文数据。

    Args:
        doi (str): 论文 DOI

    Returns:
        dict: 包含标题、年份、作者、引用关系的数据
              返回空字典表示请求失败
    """
    s2_fields = 'title,year,venue,authors,citations.externalIds,references.externalIds'
    try:
        s2_res = requests.get(
            f"{S2_API_URL}{doi}",
            params={'fields': s2_fields},
            headers=HEADERS,
            timeout=15
        )
        if s2_res.status_code == 200:
            return s2_res.json() or {}
    except Exception as e:
        print(f"  [S2 异常] {doi}: {e}")

    return {}


def fetch_crossref(doi):
    """
    从 Crossref API 获取论文数据。

    Args:
        doi (str): 论文 DOI

    Returns:
        dict: 包含元数据和引用关系的数据
              返回空字典表示请求失败
    """
    try:
        cr_res = requests.get(
            f"{CR_API_URL}{doi}",
            headers=HEADERS,
            timeout=15
        )
        if cr_res.status_code == 200:
            return cr_res.json().get('message') or {}
    except Exception as e:
        print(f"  [Crossref 异常] {doi}: {e}")

    return {}


def fetch_opencitations(doi):
    """
    从 OpenCitations API 获取论文的被引和引用 DOI 列表。

    Args:
        doi (str): 论文 DOI

    Returns:
        dict: 包含 DOI 列表的数据
              格式：{
                  'citations': ['doi1', 'doi2', ...],    # 谁引用了这篇论文 (citing字段)
                  'references': ['doi3', 'doi4', ...]    # 这篇论文引用了谁 (cited字段)
              }
              返回空字典表示请求失败
    """
    result = {
        'citations': [],      # 谁引用了这篇论文 (cited方的citing字段)
        'references': []      # 这篇论文引用了谁 (citing方的cited字段)
    }

    # 获取被引 (Citations): 谁引用了这篇论文
    try:
        citations_res = requests.get(
            f"{OC_CITATIONS_URL}{doi}",
            headers=HEADERS,
            timeout=15
        )
        if citations_res.status_code == 200:
            citations_data = citations_res.json()
            if isinstance(citations_data, list):
                # 提取 "citing" 字段 (谁引用了这篇论文)
                for item in citations_data:
                    if isinstance(item, dict):
                        citing_doi = item.get('citing')
                        if citing_doi:
                            result['citations'].append(citing_doi.lower())
    except Exception as e:
        print(f"  [OpenCitations 被引异常] {doi}: {e}")

    time.sleep(REQUEST_DELAY / 2)  # 较小的延迟

    # 获取引用 (References): 这篇论文引用了谁
    try:
        references_res = requests.get(
            f"{OC_REFERENCES_URL}{doi}",
            headers=HEADERS,
            timeout=15
        )
        if references_res.status_code == 200:
            references_data = references_res.json()
            if isinstance(references_data, list):
                # 提取 "cited" 字段 (这篇论文引用了谁)
                for item in references_data:
                    if isinstance(item, dict):
                        cited_doi = item.get('cited')
                        if cited_doi:
                            result['references'].append(cited_doi.lower())
    except Exception as e:
        print(f"  [OpenCitations 引用异常] {doi}: {e}")

    return result



def fetch_combined_data(doi):
    """
    深度融合抓取逻辑（极致防错版）：
    1. 同时发起 S2、Crossref 和 OpenCitations 请求。
    2. 严格检查每个层级的 NoneType 和数据类型。
    3. 合并三个数据源的元数据和引用列表。

    数据源优先级：
    - 元数据：S2 > Crossref
    - 引用关系：S2 + Crossref + OpenCitations
    """
    doi = doi.lower().strip()
    f_set, b_set = set(), set()
    metadata = {}

    # --- 1. 获取原始响应 ---
    s2_data = fetch_semanticscholar(doi)
    time.sleep(REQUEST_DELAY)
    cr_data = fetch_crossref(doi)
    time.sleep(REQUEST_DELAY)
    oc_data = fetch_opencitations(doi)


# --- 2. 元数据融合 ---
    # 安全获取 Crossref 的列表字段
    cr_titles = cr_data.get('title')
    cr_journals = cr_data.get('container-title')
    
    # 填充标题：S2 优先，若无则取 Crossref 列表的第一个元素（如果存在）
    metadata['title'] = s2_data.get('title') or (cr_titles[0] if isinstance(cr_titles, list) and cr_titles else None)
    
    # 填充年份
    metadata['year'] = s2_data.get('year') or cr_data.get('published-print', {}).get('date-parts', [[None]])[0][0]
    
    # 填充期刊：S2 (venue) 优先，若无则取 Crossref 的 container-title 第一个元素
    metadata['journal'] = s2_data.get('venue') or (cr_journals[0] if isinstance(cr_journals, list) and cr_journals else None)
    
    # 填充作者
    s2_authors = s2_data.get('authors')
    if isinstance(s2_authors, list):
        metadata['authors'] = [a.get('name') for a in s2_authors if isinstance(a, dict) and a.get('name')]
    else:
        metadata['authors'] = []

    # --- 3. 引用数据全量合并（严格防错） ---
    
    # 从 S2 提取
    # 处理 Citations (Forward)
    s2_citations = s2_data.get('citations')
    if isinstance(s2_citations, list):
        for cit in s2_citations:
            if isinstance(cit, dict):
                # 再次检查 externalIds 是否为字典
                ext_ids = cit.get('externalIds')
                if isinstance(ext_ids, dict):
                    c_doi = ext_ids.get('DOI')
                    if c_doi: f_set.add(c_doi.lower())

    # 处理 References (Backward)
    s2_refs = s2_data.get('references')
    if isinstance(s2_refs, list):
        for ref in s2_refs:
            if isinstance(ref, dict):
                ext_ids = ref.get('externalIds')
                if isinstance(ext_ids, dict):
                    r_doi = ext_ids.get('DOI')
                    if r_doi: b_set.add(r_doi.lower())

    # 从 Crossref 提取 (Backward)
    cr_refs = cr_data.get('reference')
    if isinstance(cr_refs, list):
        for r in cr_refs:
            if isinstance(r, dict):
                r_doi = r.get('DOI')
                if r_doi: b_set.add(r_doi.lower())

    # 从 OpenCitations 提取
    # Citations: 谁引用了这篇论文 (Backward)
    oc_citations = oc_data.get('citations', [])
    if isinstance(oc_citations, list):
        for citing_doi in oc_citations:
            if citing_doi:
                b_set.add(citing_doi.lower())

    # References: 这篇论文引用了谁 (Forward)
    oc_refs = oc_data.get('references', [])
    if isinstance(oc_refs, list):
        for cited_doi in oc_refs:
            if cited_doi:
                f_set.add(cited_doi.lower())


    # --- 4. 有效性检查 ---
    if not metadata.get('title') and not b_set and not f_set:
        return None

    return {
        "doi": doi,
        "metadata": metadata,
        "forward": list(f_set),
        "backward": list(b_set),
        "last_updated": datetime.now().strftime("%Y-%m-%d")
    }

from graph_utils import calculate_jaccard

def run_miner(seeds,force_update=False):
    db = load_db()
    queue = [(d.lower(), 0) for d in seeds]
    processed_session = set()

    while queue:
        curr_doi, depth = queue.pop(0)
        if curr_doi in processed_session: continue
        
        print(f"\n[层级 {depth}] 正在处理: {curr_doi}")

        # 检查缓存与有效期
        if curr_doi in db and not is_expired(db[curr_doi].get('last_updated')) and not force_update:
            print(f"  使用本地缓存数据")
            curr_data = db[curr_doi]
        else:
            curr_data = fetch_combined_data(curr_doi)
            if curr_data:
                db[curr_doi] = curr_data
                upsert_paper(curr_data)
            else:
                print(f"  跳过: 无法获取数据")
                continue

        # 达到深度上限则不作为种子扩散
        if depth >= MAX_DEPTH:
            processed_session.add(curr_doi)
            continue

        # 处理邻居并计算相似度
        for key in ["forward", "backward"]:
            classified_key = f"classified_{key}"
            db[curr_doi][classified_key] = []
            
            neighbor_list = curr_data.get(key, [])
            print(f"  分析 {key} 邻居 (共 {len(neighbor_list)} 篇)...")

            for n_doi in neighbor_list:
                # 预获取邻居信息以计算 Jaccard
                if n_doi in db and not is_expired(db[n_doi].get('last_updated')) and not force_update:
                    n_data = db[n_doi]
                else:
                    n_data = fetch_combined_data(n_doi)
                    if n_data:
                        db[n_doi] = n_data
                        upsert_paper(n_data)
                        time.sleep(REQUEST_DELAY)
                
                if not n_data: continue

                # 计算相似度系数
                coeff = calculate_jaccard(curr_data['backward'], n_data['backward'])
                db[curr_doi][classified_key].append({"doi": n_doi, "coefficient": coeff})

                # 阈值判断
                if coeff >= THRESHOLD and n_doi not in processed_session:
                    if not any(q[0] == n_doi for q in queue):
                        print(f"    找到高相关邻居: {n_doi} (Sim: {coeff})")
                        queue.append((n_doi, depth + 1))

        processed_session.add(curr_doi)
        upsert_paper(db[curr_doi])

    print("\n[任务完成] 学术图谱已更新。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="学术图谱挖掘 - 从 DOI 列表构建引用网络",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法：
  # 使用 doi_list.txt 文件
  python fitch_citations.py

  # 指定自定义 DOI 列表文件
  python fitch_citations.py --file my_dois.txt

  # 直接指定 DOI
  python fitch_citations.py --doi 10.1038/nphys2439 10.1103/PhysRevLett.92.185001

  # 查看所有选项
  python fitch_citations.py --help
        """
    )

    parser.add_argument(
        "--file",
        type=str,
        default="doi_list.txt",
        help="DOI 列表文件路径（默认：doi_list.txt）"
    )
    parser.add_argument(
        "--force-update",
        action="store_true",
        help="强制更新所有 DOI 的数据，即使本地缓存未过期"
    )

    parser.add_argument(
        "--doi",
        nargs="+",
        help="直接指定 DOI（空格分隔），不读取文件"
    )

    args = parser.parse_args()

    # 获取 DOI 列表
    seeds = []

    if args.doi:
        # 直接指定 DOI
        seeds = args.doi
        print(f"📝 使用命令行指定的 {len(seeds)} 个 DOI")
    else:
        # 从文件读取
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 跳过空行和注释
                    if line and not line.startswith('#'):
                        seeds.append(line)
            print(f"📖 从 {args.file} 读取 {len(seeds)} 个 DOI")
        except FileNotFoundError:
            print(f"❌ 错误：文件 {args.file} 不存在")
            print(f"📝 请创建 {args.file} 文件，每行一个 DOI")
            sys.exit(1)
        except Exception as e:
            print(f"❌ 读取文件出错：{e}")
            sys.exit(1)

    if not seeds:
        print("❌ 错误：没有找到任何 DOI")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("🚀 开始构建学术图谱")
    print("=" * 60)
    print(f"种子论文数：{len(seeds)}")
    print(f"阈值：{THRESHOLD}")
    print(f"最大深度：{MAX_DEPTH}")
    print("=" * 60 + "\n")

    run_miner(seeds, force_update=args.force_update)