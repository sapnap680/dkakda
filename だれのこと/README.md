# 出勤管理システム

Firebase と位置情報を使った出勤記録システム

## 🔗 URL

- **出勤記録**: `/attendance.html`
- **管理画面**: `/admin.html`

## 📋 機能

### 出勤記録ページ
- 名前入力（登録済みの名前のみ）
- 交通経路選択（家→事務所 / 学校→事務所）
- 位置情報による自動チェック（200m以内）

### 管理画面
- 本日の出勤状況
- 人員管理（追加・削除）
- 出勤統計
- 月次レポート（印刷可能）

## 🚀 デプロイ

### Vercel
[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone)

### Firebase Hosting
```bash
firebase init hosting
firebase deploy
```

## 🔧 設定

Firebase設定は各HTMLファイルの `firebaseConfig` オブジェクトで設定されています。

## 📱 使い方

1. 管理画面で人員を登録
2. 出勤記録ページで日々の出勤を記録
3. 月次レポートで集計・印刷




