import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import re
import time
import argparse
from urllib.parse import urljoin
import getpass
from datetime import datetime
import json

# 既存のJBA検証システムのインポート
import sys
sys.path.append('.')

class IntegratedTournamentSystem:
    """大会IDからJBA照合まで一括処理する統合システム"""
    
    def __init__(self, jba_system, validator):
        self.jba_system = jba_system
        self.validator = validator
        self.base_url = "https://www.kcbbf.jp"
        
    def login_and_get_tournament_csvs(self, username, password, game_id):
        """ログインして大会の全CSVを取得"""
        
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        })
        
        try:
            # ログイン処理
            st.info("🔐 ログイン処理中...")
            login_url = f"{self.base_url}/restrict/login"
            login_page = session.get(login_url, timeout=30)
            
            if login_page.status_code != 200:
                st.error("❌ ログインページにアクセスできません")
                return None
            
            soup = BeautifulSoup(login_page.text, "html.parser")
            form = soup.find("form")
            
            if not form:
                st.error("❌ ログインフォームが見つかりません")
                return None
            
            # ログイン実行
            form_action = f"{self.base_url}/master-admin/login"
            login_data = {"uid": username, "pass": password}
            session.headers.update({"Referer": login_url})
            
            login_response = session.post(form_action, data=login_data, timeout=30)
            
            if "login" in login_response.url.lower():
                st.error("❌ ログインに失敗しました")
                return None
            
            st.success("✅ ログインに成功しました！")
            
            # 大会CSV取得
            st.info(f"🏀 大会ID {game_id} のCSVを取得中...")
            target_url = f"{self.base_url}/master-admin-game_category_teams/index/search/true/game_category_id/{game_id}"
            
            response = session.get(target_url, timeout=30)
            if response.status_code != 200:
                st.error(f"❌ 大会ページにアクセスできません (ステータス: {response.status_code})")
                return None
            
            if "404" in response.text or "Error" in response.text:
                st.error("❌ 大会が見つかりませんでした")
                return None
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # CSVリンクを抽出
            csv_links = []
            for a in soup.find_all("a", href=True):
                href = a.get("href")
                if href and "/master-admin-game_category_teams/csv/id/" in href:
                    if href.startswith("/"):
                        full_url = f"{self.base_url}{href}"
                    else:
                        full_url = href
                    csv_links.append(full_url)
            
            st.info(f"📊 {len(csv_links)} 件のCSVリンクを検出")
            
            if not csv_links:
                st.warning("⚠️ CSVリンクが見つかりませんでした")
                return None
            
            # CSVを取得してDataFrameに変換
            all_universities_data = []
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, csv_url in enumerate(csv_links):
                try:
                    status_text.text(f"CSV {i+1}/{len(csv_links)} を取得中...")
                    
                    csv_response = session.get(csv_url, timeout=30)
                    csv_response.raise_for_status()
                    
                    # CSVをDataFrameに変換
                    df = pd.read_csv(pd.StringIO(csv_response.text))
                    
                    # 大学名を取得
                    content_disposition = csv_response.headers.get("content-disposition", "")
                    filename_match = re.search(r'filename="(.+)"', content_disposition)
                    
                    if filename_match:
                        university_name = filename_match.group(1).replace('.csv', '')
                    else:
                        university_name = f"大学_{i+1}"
                    
                    # 大学名をDataFrameに追加
                    df['大学名'] = university_name
                    all_universities_data.append(df)
                    
                    progress = (i + 1) / len(csv_links)
                    progress_bar.progress(progress)
                    
                    time.sleep(0.5)  # サーバー負荷軽減
                    
                except Exception as e:
                    st.warning(f"⚠️ CSV {i+1} の取得に失敗: {str(e)}")
                    continue
            
            progress_bar.progress(1.0)
            status_text.text("✅ CSV取得完了")
            
            if all_universities_data:
                # 全大学のデータを結合
                combined_df = pd.concat(all_universities_data, ignore_index=True)
                st.success(f"✅ {len(all_universities_data)} 大学のデータを取得しました")
                return combined_df
            else:
                return None
                
        except Exception as e:
            st.error(f"❌ エラー: {str(e)}")
            return None
    
    def process_tournament_data(self, df, university_name=None):
        """大会データをJBA照合で処理"""
        
        if df is None or df.empty:
            st.error("❌ 処理するデータがありません")
            return None
        
        st.info("🔍 JBA照合処理を開始...")
        
        # 大学ごとに処理
        universities = df['大学名'].unique() if '大学名' in df.columns else [university_name or "Unknown"]
        
        all_results = []
        
        for univ in universities:
            st.info(f"🏫 {univ} を処理中...")
            
            # 大学のデータを抽出
            if '大学名' in df.columns:
                univ_data = df[df['大学名'] == univ].copy()
            else:
                univ_data = df.copy()
            
            # JBA照合処理
            results = []
            
            for index, row in univ_data.iterrows():
                # 選手名を取得
                player_name = None
                name_columns = ['選手名', '氏名', 'name', 'Name']
                
                for col in name_columns:
                    if col in univ_data.columns and pd.notna(row[col]):
                        player_name = str(row[col]).strip()
                        break
                
                if not player_name:
                    results.append({
                        'index': index,
                        'original_data': row.to_dict(),
                        'status': 'missing_data',
                        'message': '選手名が取得できませんでした',
                        'correction': None
                    })
                    continue
                
                # JBA照合
                verification_result = self.jba_system.verify_player_info(
                    player_name, None, univ, get_details=True, threshold=1.0
                )
                
                result = {
                    'index': index,
                    'original_data': row.to_dict(),
                    'verification_result': verification_result,
                    'status': verification_result['status'],
                    'university': univ
                }
                
                # 完全一致の場合
                if verification_result['status'] == 'match':
                    if 'jba_data' in verification_result:
                        jba_data = verification_result['jba_data']
                        is_valid, validation_issues, school_corrections = self.validator.validate_player_data(jba_data)
                        
                        corrected_data = row.to_dict().copy()
                        
                        # JBA情報を追加
                        if 'height' in jba_data and jba_data['height']:
                            corrected_data['身長'] = f"{jba_data['height']}cm"
                        if 'weight' in jba_data and jba_data['weight']:
                            corrected_data['体重'] = f"{jba_data['weight']}kg"
                        if 'position' in jba_data and jba_data['position']:
                            corrected_data['ポジション'] = jba_data['position']
                        if 'school' in jba_data and jba_data['school']:
                            if 'school' in school_corrections:
                                corrected_data['出身校'] = school_corrections['school']
                            else:
                                corrected_data['出身校'] = jba_data['school']
                        if 'grade' in jba_data and jba_data['grade']:
                            corrected_data['学年'] = jba_data['grade']
                        if 'uniform_number' in jba_data and jba_data['uniform_number']:
                            corrected_data['背番号'] = jba_data['uniform_number']
                        
                        result['correction'] = corrected_data
                        
                        if not is_valid:
                            result['validation_issues'] = validation_issues
                            result['message'] = f'JBAデータベースと完全一致（詳細情報追加）⚠️ 異常値検出: {", ".join(validation_issues)}'
                        else:
                            result['message'] = 'JBAデータベースと完全一致（詳細情報追加）'
                    else:
                        result['correction'] = None
                        result['message'] = 'JBAデータベースと完全一致'
                
                # 部分一致の場合
                elif verification_result['status'] == 'partial_match':
                    jba_data = verification_result['jba_data']
                    similarity = verification_result.get('similarity', 0.0)
                    
                    corrected_data = row.to_dict().copy()
                    
                    if 'height' in jba_data and jba_data['height']:
                        corrected_data['身長'] = f"{jba_data['height']}cm"
                    if 'weight' in jba_data and jba_data['weight']:
                        corrected_data['体重'] = f"{jba_data['weight']}kg"
                    if 'position' in jba_data and jba_data['position']:
                        corrected_data['ポジション'] = jba_data['position']
                    if 'school' in jba_data and jba_data['school']:
                        corrected_data['出身校'] = jba_data['school']
                    if 'grade' in jba_data and jba_data['grade']:
                        corrected_data['学年'] = jba_data['grade']
                    if 'uniform_number' in jba_data and jba_data['uniform_number']:
                        corrected_data['背番号'] = jba_data['uniform_number']
                    
                    result['correction'] = corrected_data
                    result['message'] = f"部分一致: {jba_data['name']} (類似度: {similarity:.3f}) - 手動確認推奨"
                
                # 一致なしの場合
                else:
                    result['correction'] = None
                    result['message'] = verification_result.get('message', '照合できませんでした')
                
                results.append(result)
            
            all_results.extend(results)
        
        return all_results
    
    def create_university_reports(self, results):
        """大学ごとのレポートを作成"""
        
        if not results:
            st.error("❌ 処理結果がありません")
            return None
        
        # 大学ごとにグループ化
        universities = {}
        for result in results:
            univ = result.get('university', 'Unknown')
            if univ not in universities:
                universities[univ] = []
            universities[univ].append(result)
        
        reports = {}
        
        for univ, univ_results in universities.items():
            # 統計情報を計算
            total_players = len(univ_results)
            match_count = len([r for r in univ_results if r['status'] == 'match'])
            partial_match_count = len([r for r in univ_results if r['status'] == 'partial_match'])
            not_found_count = len([r for r in univ_results if r['status'] == 'not_found'])
            
            # レポートデータを作成
            report_data = {
                'university': univ,
                'total_players': total_players,
                'match_count': match_count,
                'partial_match_count': partial_match_count,
                'not_found_count': not_found_count,
                'match_rate': (match_count / total_players * 100) if total_players > 0 else 0,
                'results': univ_results
            }
            
            reports[univ] = report_data
        
        return reports
    
    def _generate_university_report(self, university_name, report):
        """単一大学のレポートを生成"""
        html_content = f"""
        <html>
        <head>
            <title>{university_name} 選手データ</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .stats {{ display: flex; justify-content: space-around; margin-bottom: 30px; }}
                .stat-box {{ text-align: center; padding: 10px; border: 1px solid #ccc; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .page-break {{ page-break-before: always; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{university_name} 選手データ</h1>
                <p>生成日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}</p>
            </div>
            
            <div class="stats">
                <div class="stat-box">
                    <h3>総選手数</h3>
                    <p>{report['total_players']}</p>
                </div>
                <div class="stat-box">
                    <h3>完全一致</h3>
                    <p>{report['match_count']}</p>
                </div>
                <div class="stat-box">
                    <h3>部分一致</h3>
                    <p>{report['partial_match_count']}</p>
                </div>
                <div class="stat-box">
                    <h3>未発見</h3>
                    <p>{report['not_found_count']}</p>
                </div>
                <div class="stat-box">
                    <h3>一致率</h3>
                    <p>{report['match_rate']:.1f}%</p>
                </div>
            </div>
            
            <h2>選手詳細データ</h2>
            <table>
                <tr>
                    <th>選手名</th>
                    <th>身長</th>
                    <th>体重</th>
                    <th>ポジション</th>
                    <th>出身校</th>
                    <th>学年</th>
                    <th>背番号</th>
                    <th>照合結果</th>
                </tr>
        """
        
        for result in report['results']:
            data = result['original_data']
            message = result.get('message', '')
            
            html_content += f"""
                <tr>
                    <td>{data.get('選手名', data.get('氏名', ''))}</td>
                    <td>{data.get('身長', '')}</td>
                    <td>{data.get('体重', '')}</td>
                    <td>{data.get('ポジション', '')}</td>
                    <td>{data.get('出身校', '')}</td>
                    <td>{data.get('学年', '')}</td>
                    <td>{data.get('背番号', '')}</td>
                    <td>{message}</td>
                </tr>
            """
        
        html_content += """
            </table>
        </body>
        </html>
        """
        
        return html_content
    
    def _generate_all_universities_report(self, reports):
        """全大学の一括レポートを生成"""
        html_content = f"""
        <html>
        <head>
            <title>全大学選手データ一覧</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .university-section {{ margin-bottom: 50px; page-break-before: always; }}
                .university-section:first-child {{ page-break-before: auto; }}
                .stats {{ display: flex; justify-content: space-around; margin-bottom: 30px; }}
                .stat-box {{ text-align: center; padding: 10px; border: 1px solid #ccc; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .university-title {{ background-color: #4CAF50; color: white; padding: 15px; text-align: center; font-size: 18px; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>全大学選手データ一覧</h1>
                <p>生成日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}</p>
                <p>総大学数: {len(reports)} 大学</p>
            </div>
        """
        
        # 全大学の統計情報
        total_players = sum(report['total_players'] for report in reports.values())
        total_matches = sum(report['match_count'] for report in reports.values())
        total_partial = sum(report['partial_match_count'] for report in reports.values())
        total_not_found = sum(report['not_found_count'] for report in reports.values())
        overall_match_rate = (total_matches / total_players * 100) if total_players > 0 else 0
        
        html_content += f"""
            <div class="stats">
                <div class="stat-box">
                    <h3>総選手数</h3>
                    <p>{total_players}</p>
                </div>
                <div class="stat-box">
                    <h3>完全一致</h3>
                    <p>{total_matches}</p>
                </div>
                <div class="stat-box">
                    <h3>部分一致</h3>
                    <p>{total_partial}</p>
                </div>
                <div class="stat-box">
                    <h3>未発見</h3>
                    <p>{total_not_found}</p>
                </div>
                <div class="stat-box">
                    <h3>全体一致率</h3>
                    <p>{overall_match_rate:.1f}%</p>
                </div>
            </div>
        """
        
        # 各大学のデータ
        for univ_name, report in reports.items():
            html_content += f"""
                <div class="university-section">
                    <div class="university-title">{univ_name}</div>
                    
                    <div class="stats">
                        <div class="stat-box">
                            <h4>総選手数</h4>
                            <p>{report['total_players']}</p>
                        </div>
                        <div class="stat-box">
                            <h4>完全一致</h4>
                            <p>{report['match_count']}</p>
                        </div>
                        <div class="stat-box">
                            <h4>部分一致</h4>
                            <p>{report['partial_match_count']}</p>
                        </div>
                        <div class="stat-box">
                            <h4>未発見</h4>
                            <p>{report['not_found_count']}</p>
                        </div>
                        <div class="stat-box">
                            <h4>一致率</h4>
                            <p>{report['match_rate']:.1f}%</p>
                        </div>
                    </div>
                    
                    <h3>選手詳細データ</h3>
                    <table>
                        <tr>
                            <th>選手名</th>
                            <th>身長</th>
                            <th>体重</th>
                            <th>ポジション</th>
                            <th>出身校</th>
                            <th>学年</th>
                            <th>背番号</th>
                            <th>照合結果</th>
                        </tr>
            """
            
            for result in report['results']:
                data = result['original_data']
                message = result.get('message', '')
                
                html_content += f"""
                    <tr>
                        <td>{data.get('選手名', data.get('氏名', ''))}</td>
                        <td>{data.get('身長', '')}</td>
                        <td>{data.get('体重', '')}</td>
                        <td>{data.get('ポジション', '')}</td>
                        <td>{data.get('出身校', '')}</td>
                        <td>{data.get('学年', '')}</td>
                        <td>{data.get('背番号', '')}</td>
                        <td>{message}</td>
                    </tr>
                """
            
            html_content += """
                    </table>
                </div>
            """
        
        html_content += """
        </body>
        </html>
        """
        
        return html_content

def main():
    """メイン処理"""
    st.title("🏀 大会統合システム")
    st.markdown("---")
    
    # サイドバーで設定
    st.sidebar.header("⚙️ 設定")
    
    # ログイン情報
    st.sidebar.subheader("🔐 ログイン情報")
    username = st.sidebar.text_input("ログインID", value="kcbf")
    password = st.sidebar.text_input("パスワード", value="sakura272", type="password")
    
    # 大会ID
    st.sidebar.subheader("🏀 大会設定")
    game_id = st.sidebar.number_input("大会ID", value=76, min_value=1)
    
    # 処理開始ボタン
    if st.sidebar.button("🚀 処理開始", type="primary"):
        
        # システム初期化
        from csv_verification_system import JBAVerificationSystem, DataValidator
        
        jba_system = JBAVerificationSystem()
        validator = DataValidator()
        integrated_system = IntegratedTournamentSystem(jba_system, validator)
        
        # ステップ1: CSV取得
        st.header("📥 ステップ1: 大会CSV取得")
        df = integrated_system.login_and_get_tournament_csvs(username, password, game_id)
        
        if df is not None:
            st.success(f"✅ {len(df)} 件のデータを取得しました")
            
            # ステップ2: JBA照合
            st.header("🔍 ステップ2: JBA照合処理")
            results = integrated_system.process_tournament_data(df)
            
            if results:
                st.success(f"✅ {len(results)} 件の照合が完了しました")
                
                # ステップ3: レポート作成
                st.header("📊 ステップ3: 大学別レポート")
                reports = integrated_system.create_university_reports(results)
                
                if reports:
                    st.success(f"✅ {len(reports)} 大学のレポートを作成しました")
                    
                    # 大学選択
                    selected_univ = st.selectbox("大学を選択:", list(reports.keys()))
                    
                    if selected_univ:
                        report = reports[selected_univ]
                        
                        # 統計情報表示
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("総選手数", report['total_players'])
                        with col2:
                            st.metric("完全一致", report['match_count'])
                        with col3:
                            st.metric("部分一致", report['partial_match_count'])
                        with col4:
                            st.metric("未発見", report['not_found_count'])
                        
                        # 一致率
                        st.metric("一致率", f"{report['match_rate']:.1f}%")
                        
                        # 詳細データ表示
                        st.subheader(f"📋 {selected_univ} 詳細データ")
                        
                        # タブで分類表示
                        tab1, tab2, tab3, tab4 = st.tabs(["全詳細", "完全一致", "部分一致", "未発見"])
                        
                        with tab1:
                            st.dataframe(pd.DataFrame([r['original_data'] for r in report['results']]))
                        
                        with tab2:
                            match_results = [r for r in report['results'] if r['status'] == 'match']
                            if match_results:
                                st.dataframe(pd.DataFrame([r['original_data'] for r in match_results]))
                            else:
                                st.info("完全一致のデータはありません")
                        
                        with tab3:
                            partial_results = [r for r in report['results'] if r['status'] == 'partial_match']
                            if partial_results:
                                st.dataframe(pd.DataFrame([r['original_data'] for r in partial_results]))
                            else:
                                st.info("部分一致のデータはありません")
                        
                        with tab4:
                            not_found_results = [r for r in report['results'] if r['status'] == 'not_found']
                            if not_found_results:
                                st.dataframe(pd.DataFrame([r['original_data'] for r in not_found_results]))
                            else:
                                st.info("未発見のデータはありません")
                        
                        # 全大学一括印刷レポート
                        st.subheader("🖨️ 全大学一括印刷レポート")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            if st.button("📄 選択大学のレポートを生成"):
                                # 選択された大学のレポートを生成
                                html_content = self._generate_university_report(selected_univ, report)
                                
                                st.download_button(
                                    label="📄 HTMLレポートをダウンロード",
                                    data=html_content,
                                    file_name=f"{selected_univ}_選手データ.html",
                                    mime="text/html"
                                )
                        
                        with col2:
                            if st.button("📚 全大学一括レポートを生成", type="primary"):
                                # 全大学のレポートを生成
                                st.info("📚 全大学のレポートを生成中...")
                                
                                html_content = self._generate_all_universities_report(reports)
                                
                                st.download_button(
                                    label="📚 全大学一括HTMLレポートをダウンロード",
                                    data=html_content,
                                    file_name=f"大会ID{game_id}_全大学選手データ.html",
                                    mime="text/html"
                                )
                                
                                st.success("✅ 全大学のレポートが生成されました！")
                
                else:
                    st.error("❌ レポートの作成に失敗しました")
            else:
                st.error("❌ JBA照合処理に失敗しました")
        else:
            st.error("❌ CSV取得に失敗しました")

if __name__ == "__main__":
    main()
