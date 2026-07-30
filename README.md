# Personal Workbench

个人工作台静态网页。

## 文件说明

- `index.html`: GitHub Pages / Netlify 直接使用的网页入口。
- `data/chinese-weather-papers.json`: 中文气象期刊每日更新数据。
- `scripts/fetch_chinese_weather_papers.py`: 抓取中文气象期刊最新论文的脚本。
- `.github/workflows/update-chinese-weather-papers.yml`: GitHub Actions 定时任务。
- `personal-workbench-site/`: 保留给 Netlify Drop 或其他静态托管使用的站点目录。

## 自动更新

GitHub Actions 默认每天 UTC 23:10 运行一次，约为北京时间 07:10。它会更新中文气象期刊论文 JSON，并自动提交到仓库。
