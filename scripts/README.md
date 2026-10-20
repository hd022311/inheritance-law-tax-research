# 重跑關鍵詞初篩

需要Python 3.11以上及系統libarchive，無須將大包放進Git

```bash
JUDICIAL_WORK_DIR=/path/to/private-work \
JUDICIAL_ARCHIVE=/path/to/archive.rar \
JUDICIAL_DELETIONS=/path/to/deletions.csv \
python scripts/screen_batch.py
```

工作目錄會產生batch_work，包含所有候選原文，請存於私人位置，不要整包公開。程式只做本地初篩，不會寫入GitHub或自動建立verified資料。人工選案另整理研究卡。規則、評分是本批可追溯版本，不表示法律相關性或完整召回；需用新版刪除清單重新執行。使用記憶體暫存全文，大資料包可能需數GB記憶體
