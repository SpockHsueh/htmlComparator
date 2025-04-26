import streamlit as st
from bs4 import BeautifulSoup
import io

class HTMLComparator:
    def __init__(self):
        self.differences = []
        self.section_matches = False
    
    def load_html(self, file_data, is_file_object=True):
        """載入HTML檔案並解析"""
        try:
            if is_file_object:
                content = file_data.getvalue().decode('utf-8')
            else:
                with open(file_data, 'r', encoding='utf-8') as file:
                    content = file.read()
            return BeautifulSoup(content, 'html.parser')
        except Exception as e:
            return f"錯誤：無法載入檔案。錯誤信息：{str(e)}"
    
    def find_all_test_sections(self, soup, skip_ids=None):
        """找到所有有效的測試段落，忽略首尾無關內容和指定的測試ID"""
        # 初始化跳過ID的列表
        if skip_ids is None:
            skip_ids = []
        
        # 尋找所有的測試開始標記
        possible_test_starts = []
        paragraphs = soup.find_all('p')
        
        for p in paragraphs:
            # 檢查段落內是否有 <br> 後跟 <a name=...>
            br_tag = p.find('br')
            if not br_tag:
                continue
                
            a_tag = p.find('a', attrs={'name': True})
            if not a_tag:
                continue
            
            # 確認這是一個測試區塊的開始標記
            name = a_tag.get('name')
            
            # 跳過指定的測試ID
            if name in skip_ids:
                continue
                
            table = p.find_next('table', {'class': 'std'})
            
            if table and table.find('td', {'class': 'cttest'}):
                possible_test_starts.append({
                    'name': name,
                    'anchor': a_tag,
                    'start_p': p,
                    'table': table
                })
        
        # 如果沒有找到有效的測試區塊，返回空列表
        if not possible_test_starts:
            return []
        
        # 添加所有有效的測試區塊
        test_sections = []
        
        for section in possible_test_starts:
            test_sections.append({
                'name': section['name'],
                'anchor': section['anchor'],
                'table': section['table']
            })
        
        return test_sections
    
    def extract_test_details(self, table, test_id):
        """提取測試細節和結果"""
        if not table:
            table_html = "無表格內容"
            return None, f"測試 {test_id} 找不到相應的表格", table_html
        
        try:
            # 儲存表格 HTML 用於顯示
            table_html = str(table)
            
            # 尋找測試標題行
            title_row = table.find('tr')
            if not title_row:
                return None, f"測試 {test_id} 的表格中找不到任何行", table_html
            
            title_cell = title_row.find('td', {'class': 'cttest'})
            if not title_cell:
                return None, f"測試 {test_id} 的表格中找不到標題單元格 (class='cttest')", table_html
            
            # 提取測試標題
            test_title = title_cell.get_text(strip=True)
            
            # 提取主測試結果
            result_cell = title_row.find('td', {'class': 'stpass'})
            if result_cell:
                test_result = "Pass"
            else:
                result_cell = title_row.find('td')  # 尋找任何結果單元格
                if result_cell and result_cell != title_cell:
                    test_result = result_cell.get_text(strip=True)
                else:
                    test_result = "Unknown"
            
            # 提取所有迭代信息
            iterations = []
            iter_rows = table.find_all('tr')
            
            # 跳過標題行，處理所有迭代行
            for i in range(1, len(iter_rows)):
                row = iter_rows[i]
                iter_cell = row.find('td', {'class': 'ctsub'})
                if not iter_cell:
                    continue
                    
                # 提取迭代標題
                bullet_span = iter_cell.find('span', {'class': 'bullet'})
                iter_text = iter_cell.get_text()
                iter_title = iter_text.split('\n')[0].strip() if iter_text else ""
                
                # 提取訓練資訊和VIC
                trained_at = None
                detected_vic = None
                li_items = iter_cell.find_all('li', {'class': 'note'})
                for li in li_items:
                    text = li.get_text(strip=True)
                    if "Trained at:" in text:
                        trained_at = text
                    elif "Detected VIC:" in text:
                        detected_vic = text
                
                # 提取迭代結果
                iter_result_cell = row.find('td', {'class': 'stpass'})
                iter_result = "Pass" if iter_result_cell else "Unknown"
                
                # 提取子測試項目
                subtests = []
                subtest_table = iter_cell.find('table', {'class': 'std'})
                if subtest_table:
                    subtest_rows = subtest_table.find_all('tr')
                    for s_row in subtest_rows:
                        desc_cell = s_row.find('td', {'class': 'subtitle'})
                        if not desc_cell:
                            continue
                        
                        # 提取描述
                        span = desc_cell.find('span', recursive=False)
                        description = ""
                        if span:
                            # 有時候描述會在第二個span裡面
                            second_span = desc_cell.find_all('span')
                            if len(second_span) > 1:
                                description = second_span[1].get_text(strip=True)
                            else:
                                description = span.get_text(strip=True)
                        else:
                            description = desc_cell.get_text(strip=True)
                        
                        # 提取結果
                        result_cell = s_row.find('td', {'class': 'stpass'})
                        if result_cell:
                            result = "Pass"
                        else:
                            result_cell = s_row.find('td')
                            if result_cell and result_cell != desc_cell:
                                result = result_cell.get_text(strip=True)
                            else:
                                result = "Unknown"
                        
                        subtests.append({
                            'description': description,
                            'result': result
                        })
                
                iterations.append({
                    'title': iter_title,
                    'trained_at': trained_at,
                    'detected_vic': detected_vic,
                    'result': iter_result,
                    'subtests': subtests
                })
            
            return {
                'title': test_title,
                'result': test_result,
                'iterations': iterations
            }, None, table_html
        except Exception as e:
            # 如果提取過程中發生任何錯誤，返回None並報告錯誤
            error_msg = f"錯誤：提取測試 {test_id} 細節時發生異常: {str(e)}"
            return None, error_msg, table_html
    
    def compare_structure(self, sample_table, target_table, test_name):
        """比較區塊結構（除name, ctsub, note外的屬性）"""
        differences = []
        
        # 比較表格的類別
        if sample_table.get('class') != target_table.get('class'):
            differences.append(f"測試 {test_name} 表格類別不同：樣本為 {sample_table.get('class')}, 目標為 {target_table.get('class')}")
        
        # 比較表格中的行數
        sample_rows = sample_table.find_all('tr')
        target_rows = target_table.find_all('tr')
        
        if len(sample_rows) != len(target_rows):
            differences.append(f"測試 {test_name} 表格行數不同：樣本有 {len(sample_rows)} 行，目標有 {len(target_rows)} 行")
        
        # 比較表格中的列數
        for i, (s_row, t_row) in enumerate(zip(sample_rows, target_rows)):
            s_cells = s_row.find_all('td')
            t_cells = t_row.find_all('td')
            
            if len(s_cells) != len(t_cells):
                differences.append(f"測試 {test_name} 第 {i+1} 行列數不同：樣本有 {len(s_cells)} 列，目標有 {len(t_cells)} 列")
        
        return differences
    
    def compare_tests(self, sample_details, target_details, test_name):
        """比較測試細節，回傳差異列表"""
        differences = []
        
        # 檢查主要測試結果
        if sample_details.get('result') != target_details.get('result'):
            differences.append(f"測試 {test_name} 主測試結果不同：樣本為 {sample_details.get('result')}, 目標為 {target_details.get('result')}")
            
            # 特別標記非Pass的項目
            if target_details.get('result') != "Pass":
                differences.append(f"注意：目標文件的測試 {test_name} 主測試結果不是 Pass，而是 {target_details.get('result')}")
        
        # 檢查迭代信息
        sample_iterations = sample_details.get('iterations', [])
        target_iterations = target_details.get('iterations', [])
        
        if len(sample_iterations) != len(target_iterations):
            differences.append(f"測試 {test_name} 迭代數量不同：樣本有 {len(sample_iterations)} 個迭代，目標有 {len(target_iterations)} 個迭代")
            
        # 比較每個迭代
        min_iter_len = min(len(sample_iterations), len(target_iterations))
        for i in range(min_iter_len):
            s_iter = sample_iterations[i]
            t_iter = target_iterations[i]
            
            iter_num = i + 1
            
            # 比較迭代標題
            if s_iter.get('title') != t_iter.get('title'):
                differences.append(f"測試 {test_name} 迭代 {iter_num} 標題不同：\n樣本：{s_iter.get('title')}\n目標：{t_iter.get('title')}")
            
            # 比較訓練資訊
            if s_iter.get('trained_at') != t_iter.get('trained_at'):
                differences.append(f"測試 {test_name} 迭代 {iter_num} 訓練資訊不同：\n樣本：{s_iter.get('trained_at')}\n目標：{t_iter.get('trained_at')}")
            
            # 比較VIC
            if s_iter.get('detected_vic') != t_iter.get('detected_vic'):
                differences.append(f"測試 {test_name} 迭代 {iter_num} 檢測到的VIC不同：\n樣本：{s_iter.get('detected_vic')}\n目標：{t_iter.get('detected_vic')}")
            
            # 比較迭代結果
            if s_iter.get('result') != t_iter.get('result'):
                differences.append(f"測試 {test_name} 迭代 {iter_num} 結果不同：\n樣本：{s_iter.get('result')}\n目標：{t_iter.get('result')}")
                
                # 特別標記非Pass的項目  
                if t_iter.get('result') != "Pass":
                    differences.append(f"注意：目標文件的測試 {test_name} 迭代 {iter_num} 結果不是 Pass，而是 {t_iter.get('result')}")
            
            # 檢查區塊內核心屬性是否一致，才進一步比對子測試
            core_attributes_match = (
                s_iter.get('title') == t_iter.get('title') and
                s_iter.get('trained_at') == t_iter.get('trained_at') and
                s_iter.get('detected_vic') == t_iter.get('detected_vic')
            )
            
            if core_attributes_match:
                # 比較子測試項目
                s_subtests = s_iter.get('subtests', [])
                t_subtests = t_iter.get('subtests', [])
                
                if len(s_subtests) != len(t_subtests):
                    differences.append(f"測試 {test_name} 迭代 {iter_num} 子測試數量不同：樣本有 {len(s_subtests)} 項，目標有 {len(t_subtests)} 項")
                
                # 比較子測試
                min_sub_len = min(len(s_subtests), len(t_subtests))
                for j in range(min_sub_len):
                    s_test = s_subtests[j]
                    t_test = t_subtests[j]
                    
                    subtest_num = j + 1
                    
                    if s_test.get('description') != t_test.get('description'):
                        differences.append(f"測試 {test_name} 迭代 {iter_num} 子測試 {subtest_num} 描述不同：\n樣本：{s_test.get('description')}\n目標：{t_test.get('description')}")
                    
                    if s_test.get('result') != t_test.get('result'):
                        differences.append(f"測試 {test_name} 迭代 {iter_num} 子測試 {subtest_num} 結果不同：\n樣本：{s_test.get('result')}\n目標：{t_test.get('result')}")
                        
                        # 特別標記非Pass的項目
                        if t_test.get('result') != "Pass":
                            differences.append(f"注意：目標文件的測試 {test_name} 迭代 {iter_num} 子測試 {subtest_num} 結果不是 Pass，而是 {t_test.get('result')}")
            else:
                differences.append(f"測試 {test_name} 迭代 {iter_num} 核心屬性不同，跳過子測試比對")
        
        return differences
    
    def compare_html_files(self, sample_file, target_file, specific_test_id=None, is_file_object=True):
        """比較兩個HTML檔案中的測試段落"""
        # 載入和解析檔案
        sample_soup = self.load_html(sample_file, is_file_object)
        target_soup = self.load_html(target_file, is_file_object)
        
        if isinstance(sample_soup, str) or isinstance(target_soup, str):
            return ["錯誤：檔案載入失敗"], False
        
        # 找到所有測試段落
        sample_sections = self.find_all_test_sections(sample_soup)
        target_sections = self.find_all_test_sections(target_soup)
        
        if not sample_sections:
            return ["錯誤：在樣本檔案中找不到任何測試段落"], False
        
        if not target_sections:
            return ["錯誤：在目標檔案中找不到任何測試段落"], False
        
        # 將測試段落轉換為字典，以便按名稱查找
        sample_sections_dict = {section['name']: section for section in sample_sections}
        target_sections_dict = {section['name']: section for section in target_sections}
        
        # 收集所有差異
        all_differences = []
        match_count = 0
        problem_count = 0
        
        # 如果指定了特定測試ID，則只比對該測試
        if specific_test_id:
            if specific_test_id not in sample_sections_dict:
                return [f"錯誤：在樣本檔案中找不到測試ID '{specific_test_id}'"], False
            
            if specific_test_id not in target_sections_dict:
                return [f"錯誤：在目標檔案中找不到測試ID '{specific_test_id}'"], False
            
            test_ids_to_compare = [specific_test_id]
        else:
            # 獲取兩個檔案中所有唯一的測試ID
            all_test_ids = set(sample_sections_dict.keys()) | set(target_sections_dict.keys())
            # 按名稱排序，使結果更容易閱讀
            test_ids_to_compare = sorted(list(all_test_ids))
        
        # 比對每個測試段落
        for test_id in test_ids_to_compare:
            # 檢查測試ID是否在兩個檔案中都存在
            in_sample = test_id in sample_sections_dict
            in_target = test_id in target_sections_dict
            
            # 如果測試ID只在目標檔案中存在，標記為差異
            if not in_sample and in_target:
                all_differences.append(f"測試 {test_id} 僅存在於目標檔案中，樣本檔案中找不到對應測試")
                problem_count += 1
                continue
            
            # 如果測試ID只在樣本檔案中存在，標記為差異
            if in_sample and not in_target:
                all_differences.append(f"測試 {test_id} 僅存在於樣本檔案中，目標檔案中找不到對應測試")
                problem_count += 1
                continue
            
            # 獲取測試段落
            sample_section = sample_sections_dict[test_id]
            target_section = target_sections_dict[test_id]
            
            # 比較表格結構
            structure_differences = self.compare_structure(
                sample_section['table'], 
                target_section['table'],
                test_id
            )
            
            if structure_differences:
                all_differences.append(f"測試 {test_id} 表格結構不同:")
                for diff in structure_differences:
                    all_differences.append(f"  - {diff}")
                problem_count += 1
                continue
            
            # 提取測試細節
            sample_result = self.extract_test_details(sample_section['table'], test_id)
            target_result = self.extract_test_details(target_section['table'], test_id)
            
            if len(sample_result) == 3:
                sample_details, sample_error, sample_html = sample_result
            else:
                sample_details, sample_error = sample_result
                sample_html = "無法獲取HTML內容"
            
            if len(target_result) == 3:
                target_details, target_error, target_html = target_result
            else:
                target_details, target_error = target_result
                target_html = "無法獲取HTML內容"
            
            if not sample_details:
                error_message = f"錯誤：無法從樣本檔案中提取測試 {test_id} 的細節"
                if sample_error:
                    error_message += f"，原因：{sample_error}"
                all_differences.append(error_message)
                # 添加HTML內容到差異列表
                all_differences.append(f"問題區塊的HTML內容:")
                all_differences.append(f"```html\n{sample_html}\n```")
                problem_count += 1
                continue
            
            if not target_details:
                error_message = f"錯誤：無法從目標檔案中提取測試 {test_id} 的細節"
                if target_error:
                    error_message += f"，原因：{target_error}"
                all_differences.append(error_message)
                # 添加HTML內容到差異列表
                all_differences.append(f"問題區塊的HTML內容:")
                all_differences.append(f"```html\n{target_html}\n```")
                problem_count += 1
                continue
            
            # 檢查測試標題是否相同
            if sample_details.get('title') != target_details.get('title'):
                all_differences.append(f"測試 {test_id} 標題不同：\n樣本：{sample_details.get('title')}\n目標：{target_details.get('title')}")
                problem_count += 1
                continue
            
            # 比較測試細節
            differences = self.compare_tests(sample_details, target_details, test_id)
            
            if differences:
                all_differences.append(f"測試 {test_id} 有以下差異:")
                for diff in differences:
                    all_differences.append(f"  - {diff}")
                problem_count += 1
            else:
                match_count += 1
                if specific_test_id:
                    all_differences.append(f"測試 {test_id} 完全匹配")
        
        # 返回結果
        if specific_test_id:
            # 單個測試匹配情況
            is_match = not problem_count
            return all_differences, is_match
        else:
            # 多個測試的總體匹配情況
            is_all_match = problem_count == 0
            
            # 添加概要信息
            if test_ids_to_compare:
                total_tests = len(test_ids_to_compare)
                only_in_sample = sum(1 for tid in test_ids_to_compare if tid in sample_sections_dict and tid not in target_sections_dict)
                only_in_target = sum(1 for tid in test_ids_to_compare if tid not in sample_sections_dict and tid in target_sections_dict)
                common_tests = total_tests - only_in_sample - only_in_target
                
                summary = f"找到總共 {total_tests} 個測試段落："
                if only_in_sample > 0:
                    summary += f"{only_in_sample} 個僅在樣本檔案中，"
                if only_in_target > 0:
                    summary += f"{only_in_target} 個僅在目標檔案中，"
                summary += f"{common_tests} 個共同測試段落中 {match_count} 個完全匹配，{common_tests - match_count} 個有差異"
                
                all_differences.insert(0, summary)
            else:
                all_differences.insert(0, "沒有找到可比對的測試段落")
            
            return all_differences, is_all_match


# 初始化 session state
if 'test_id_list' not in st.session_state:
    st.session_state.test_id_list = []

if 'test_id_comparison' not in st.session_state:
    st.session_state.test_id_comparison = None

# 設置頁面標題和布局
st.set_page_config(
    page_title="HTML 比對工具",
    page_icon="🔍",
    layout="wide"
)

# 應用標題和描述
st.title("HTML 比對工具")
st.markdown("""
這個工具可以幫助您比對兩個HTML檔案中特定測試段落的差異，根據您指定的規則進行比較。
""")

# 分成兩欄
col1, col2 = st.columns(2)

with col1:
    st.header("上傳檔案")
    
    # 文件上傳
    sample_file = st.file_uploader("上傳樣本文件", type=["html"], key="sample")
    target_file = st.file_uploader("上傳目標文件", type=["html"], key="target")
    
    # 比對模式
    compare_mode = st.radio(
        "比對模式",
        ["比對單一測試", "比對所有測試"],
        index=0,
        help="單一測試：只比對特定ID的測試段落；所有測試：比對所有找到的測試段落"
    )
    
    # 只有在單一測試模式時，才顯示測試ID輸入框
    if compare_mode == "比對單一測試":
        # 如果已經上傳了兩個文件，提取兩個文件中的測試ID
        if sample_file and target_file and not st.session_state.test_id_comparison:
            with st.spinner("分析文件中的測試ID..."):
                # 創建比對器
                comparator = HTMLComparator()
                
                # 載入樣本檔案
                sample_soup = comparator.load_html(sample_file)
                sample_ids = []
                if not isinstance(sample_soup, str):
                    sample_sections = comparator.find_all_test_sections(sample_soup)
                    sample_ids = [section['name'] for section in sample_sections]
                    sample_ids.sort()
                
                # 載入目標檔案
                target_soup = comparator.load_html(target_file)
                target_ids = []
                if not isinstance(target_soup, str):
                    target_sections = comparator.find_all_test_sections(target_soup)
                    target_ids = [section['name'] for section in target_sections]
                    target_ids.sort()
                
                # 計算共同和獨有的測試ID
                common_ids = [id for id in target_ids if id in sample_ids]
                only_in_target = [id for id in target_ids if id not in sample_ids]
                only_in_sample = [id for id in sample_ids if id not in target_ids]
                
                # 更新session state
                st.session_state.test_id_comparison = {
                    'common': common_ids,
                    'only_in_target': only_in_target,
                    'only_in_sample': only_in_sample,
                    'all_target': target_ids
                }
        
        # 如果有測試ID比較結果，顯示一個摘要
        if 'test_id_comparison' in st.session_state and st.session_state.test_id_comparison:
            with st.expander("測試ID比較摘要", expanded=False):
                comp = st.session_state.test_id_comparison
                st.write(f"共同測試ID: {len(comp['common'])} 個")
                if comp['only_in_target']:
                    st.write(f"僅在目標文件中: {len(comp['only_in_target'])} 個")
                    st.write(", ".join(comp['only_in_target'][:10]) + ("..." if len(comp['only_in_target']) > 10 else ""))
                if comp['only_in_sample']:
                    st.write(f"僅在樣本文件中: {len(comp['only_in_sample'])} 個")
                    st.write(", ".join(comp['only_in_sample'][:10]) + ("..." if len(comp['only_in_sample']) > 10 else ""))
        
        # 從目標文件中的測試ID提供下拉列表
        if 'test_id_comparison' in st.session_state and st.session_state.test_id_comparison:
            target_ids = st.session_state.test_id_comparison['all_target']
            if target_ids:
                test_id = st.selectbox(
                    "選擇測試ID (來自目標文件)",
                    options=target_ids,
                    index=0
                )
            else:
                test_id = st.text_input("輸入測試ID", value="HFR1-11")
        else:
            test_id = st.text_input("輸入測試ID", value="HFR1-11")
    else:
        test_id = None
    
    # 比對按鈕
    compare_button = st.button("比對檔案")

with col2:
    st.header("比對結果")
    
    # 初始化比對結果顯示區域
    result_container = st.container()

# 執行比對
if compare_button:
    with result_container:
        if not sample_file or not target_file:
            st.error("請上傳樣本檔案和目標檔案")
        elif compare_mode == "比對單一測試" and not test_id:
            st.error("請選擇或輸入測試ID")
        else:
            # 清空之前的結果
            st.empty()
            
            # 創建比對器並執行比對
            with st.spinner("比對中..."):
                comparator = HTMLComparator()
                specific_id = test_id if compare_mode == "比對單一測試" else None
                differences, is_match = comparator.compare_html_files(
                    sample_file, target_file, specific_id
                )
            
            # 顯示結果
            if is_match and len(differences) <= 1:  # 只有概要信息或沒有差異
                st.success("比對結果：測試數據完全相同")
                if differences and compare_mode == "比對所有測試":
                    st.info(differences[0])  # 顯示概要信息
            elif is_match and len(differences) > 1 and compare_mode == "比對單一測試":
                # 對於單一測試，如果有信息但是是匹配的
                st.success("比對結果：測試數據完全相同")
                for diff in differences:
                    st.write(diff)
            else:
                st.error("比對結果：發現差異")
                
                # 顯示所有差異
                if compare_mode == "比對所有測試" and differences:
                    # 顯示概要信息
                    st.info(differences[0])
                    
                    # 創建一個擴展區以顯示詳細差異
                    with st.expander("查看詳細差異", expanded=True):
                        for i, diff in enumerate(differences):
                            if i > 0:  # 跳過概要信息
                                st.markdown(diff)
                else:
                    # 單一測試模式或沒有概要信息
                    for diff in differences:
                        st.markdown(diff)

# 添加使用說明
st.markdown("""
---
### 使用說明

1. 上傳樣本文件（標準參考HTML檔案）
2. 上傳目標文件（需要比對的HTML檔案）
3. 選擇比對模式:
   - **比對單一測試**: 選擇或輸入測試ID，只比對該特定測試段落
   - **比對所有測試**: 比對兩個檔案中所有共同的測試段落
4. 點擊「比對檔案」按鈕開始比對

### 比對規則

工具會按照以下規則進行比對：

1. 每個比對區塊由 `<p><br><a name=...` 開始，直到下一個類似的標記
2. 比對同名測試段落的結構，檢查表格是否一致
3. 確認測試標題是否相同，以判斷是否為同一組數據
4. 比對除 name、ctsub 和 note 以外的屬性是否一致
5. 只有核心屬性一致時，才進一步比對 subtitle 部分
6. 檢查主測試結果是否為 `Pass`，如果目標文件不是 `Pass` 會特別標註
7. 檢查每個迭代中的所有子測試項目的描述和結果是否一致，並特別標註非 `Pass` 的項目
""")